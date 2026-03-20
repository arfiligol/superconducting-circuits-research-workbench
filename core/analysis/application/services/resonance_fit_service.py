"""Application service for S-Parameter resonance fitting workflows."""

import typing

import numpy as np

from core.analysis.application.services.data_record_management import (
    DataRecordManagementService,
)
from core.analysis.application.services.dataset_management import DatasetManagementService
from core.analysis.application.services.parameter_management import ParameterManagementService
from core.analysis.application.services.trace_record_materializer import materialize_trace_record
from core.analysis.domain import (
    normalize_trace_record,
    trace_record_data_type,
    trace_record_dataset_id,
    trace_record_parameter,
)
from core.analysis.domain.math.s_parameters import (
    MultiResonanceVectorFitter,
    fit_notch_s21,
    fit_transmission_s21,
    notch_s21,
    transmission_s21,
)


class ResonanceFitService:
    """Service to extract dataset information and perform S-parameter notch resonance fits."""

    def __init__(self) -> None:
        self.dataset_service = DatasetManagementService()
        self.data_record_service = DataRecordManagementService()
        self.param_service = ParameterManagementService()

    def perform_fit(
        self,
        dataset_identifier: str,
        parameter: str = "S21",
        model: str = "notch",
        resonators: int = 1,
        f_min: float | None = None,
        f_max: float | None = None,
        bias_index: int | None = None,
        record_ids: list[int] | None = None,
    ) -> dict[str, "typing.Any"]:
        """
        Perform a CPZM notch resonance fit on a given dataset and parameter.
        Uses complex representations if available, or reconstructs from magnitude/phase.
        """
        dataset = self.dataset_service.get_dataset(dataset_identifier)
        if not dataset:
            raise ValueError(f"Dataset not found: {dataset_identifier}")

        # Find matching S-parameter records
        # Ideally, we look for both real/imag representations or magnitude/phase representations.
        # But wait, our HFSS phase pipeline only parses "phase" currently,
        # let's write a robust fetcher.

        # In a real situation, we should fetch DataRecord entities and extract lists.
        # However, `DatasetDetailDTO` in our system doesn't embed the actual `values` data directly
        # to avoid payload size bursts. We need to fetch the `DataRecord` explicitly.

        # We need a method to get DataRecords by Dataset ID and parameter
        # Let's search through all records and filter (in-memory for now, assuming small DB)
        all_records = self.data_record_service.list_records(dataset.id)
        if record_ids is not None:
            selected_ids = set(record_ids)
            all_records = [
                record
                for record in all_records
                if normalize_trace_record(record).id in selected_ids
            ]
        s_records = [
            r
            for r in all_records
            if trace_record_dataset_id(r) == dataset.id
            and trace_record_data_type(r) == "s_parameters"
            and trace_record_parameter(r) == parameter
        ]

        if not s_records:
            raise ValueError(
                f"No s_parameters found for parameter {parameter} in dataset {dataset_identifier}"
            )

        # We need to construct the complex S21 and freq axis
        # First, reconstruct the records
        detailed_records = [
            self.data_record_service.get_record(int(trace_id))
            for record in s_records
            for trace_id in [normalize_trace_record(record).id]
            if trace_id is not None
        ]

        reps = {
            normalized_record.representation: normalized_record
            for record in detailed_records
            if record is not None
            for normalized_record in [materialize_trace_record(record)]
        }

        f_axis = None
        s21_complex = None

        if "real" in reps and "imaginary" in reps:
            # Reconstruct from Re/Im
            f_axis = np.array(reps["real"].axes[0]["values"], dtype=float)
            values_re = np.array(reps["real"].values, dtype=float)
            values_im = np.array(reps["imaginary"].values, dtype=float)
            s21_complex = values_re + 1j * values_im
        elif ("phase" in reps or "unwrapped_phase" in reps) and "magnitude" in reps:
            # Reconstruct from Mag/Phase
            # We assume they share the same frequency axis
            mag_record = reps["magnitude"]
            phase_key = "unwrapped_phase" if "unwrapped_phase" in reps else "phase"
            phase_record = reps[phase_key]

            f_axis = np.array(mag_record.axes[0]["values"], dtype=float)

            # HFSS magnitude is often in dB. We should check if it needs conversion to linear.
            # Assuming linear magnitude for now, but if it's dB: mag_lin = 10**(mag_dB/20)
            # The user's S-parameter files usually don't dictate dB vs lin in the representation
            # string yet, but standard is linear unless specified. We will assume linear.
            mag_vals = np.array(mag_record.values, dtype=float)
            phase_vals = np.array(
                phase_record.values, dtype=float
            )  # already in radians per phase.py

            s21_complex = mag_vals * np.exp(1j * phase_vals)
        else:
            raise ValueError(
                f"Dataset lack sufficient representations for {parameter}. "
                "Found: " + ", ".join(list(reps.keys())) + ". "
                "Need either (real, imaginary) OR (magnitude, phase/unwrapped_phase)."
            )

        # Now we have the arrays, call the math core
        # Note: Depending on the axes structure from raw HFSS, there might be
        # multiple sweep dimensions. Assuming 1D for simplicity in the current path.
        # If the array is multi-dimensional (e.g. [Freq, L_jun]),
        # extract L_jun axis metadata and slice accordingly.
        l_jun_values: list[float] | None = None
        bias_indices: list[int] = [0]

        if s21_complex.ndim > 1:
            if s21_complex.ndim > 2:
                raise ValueError("S21 resonance fitting supports at most one sweep axis.")
            n_biases = s21_complex.shape[1]

            # Try to extract L_jun values from axes[1]
            any_rep = next(iter(reps.values()))
            if len(any_rep.axes) > 1 and str(any_rep.axes[1].get("name", "")).lower() in {
                "l_jun",
                "l_ind",
            }:
                l_jun_values = [float(v) for v in any_rep.axes[1]["values"]]
            else:
                l_jun_values = None

            if bias_index is not None:
                if bias_index >= n_biases:
                    raise ValueError(
                        f"Selected bias_index {bias_index} is out of bounds "
                        f"for data with {n_biases} bias points."
                    )
                bias_indices = [bias_index]
            else:
                bias_indices = list(range(n_biases))

        # Base frequency axis (Hz)
        f_base = f_axis.flatten() * 1e9

        extra_context = {
            "model": model,
            "resonators": resonators,
            "f_min": f_min,
            "f_max": f_max,
        }

        # Run fitting per bias slice
        slice_results: list[dict[str, typing.Any]] = []

        for bi in bias_indices:
            # Extract the 1D slice for this bias point
            if s21_complex.ndim > 1:
                s21_slice = s21_complex[:, bi].flatten()
            else:
                s21_slice = s21_complex.flatten()

            f_arr = f_base.copy()
            s21_arr = s21_slice

            # Mask out NaNs
            valid = ~np.isnan(f_arr) & ~np.isnan(s21_arr)

            # Apply user-defined frequency window (converted from GHz to Hz)
            if f_min is not None:
                valid &= f_arr >= f_min * 1e9
            if f_max is not None:
                valid &= f_arr <= f_max * 1e9

            f_arr = f_arr[valid]
            s21_arr = s21_arr[valid]

            if len(f_arr) < 5:
                continue  # Skip slices with too few points

            # Fit
            result: dict[str, typing.Any] = {}
            if model == "notch":
                result = fit_notch_s21(f_arr, s21_arr)
                method_name = f"complex_notch_fit_{parameter}"
            elif model == "transmission":
                result = fit_transmission_s21(f_arr, s21_arr)
                method_name = f"transmission_fit_{parameter}"
            elif model == "vf":
                fitter = MultiResonanceVectorFitter(f_arr, s21_arr)
                result = fitter.fit(n_resonators=resonators)
                method_name = f"vector_fit_{parameter}"
            else:
                raise ValueError(f"Unsupported model: {model}")

            # Persist parameters (suffix with bias index when multiple slices)
            suffix = f"_b{bi}" if len(bias_indices) > 1 else ""
            l_jun_val = l_jun_values[bi] if l_jun_values and bi < len(l_jun_values) else None
            param_extra = {
                **extra_context,
                "sweep_index": bi,
                "sweep_axis": "L_jun" if l_jun_val is not None else None,
                "sweep_value": l_jun_val,
            }

            if model in ["notch", "transmission"]:
                self.param_service.create_or_update_param(
                    dataset.id,
                    name=f"mode_1_ghz{suffix}",
                    value=result["fr"] / 1e9,
                    unit="GHz",
                    device_type="resonator",
                    method=method_name,
                    extra=param_extra,
                )
                self.param_service.create_or_update_param(
                    dataset.id,
                    name=f"Ql{suffix}",
                    value=result["Ql"],
                    unit="",
                    device_type="resonator",
                    method=method_name,
                    extra=param_extra,
                )
                self.param_service.create_or_update_param(
                    dataset.id,
                    name=f"Qc{suffix}",
                    value=result.get("Qc_mag", float("inf")),
                    unit="",
                    device_type="resonator",
                    method=method_name,
                    extra=param_extra,
                )
                self.param_service.create_or_update_param(
                    dataset.id,
                    name=f"Qi{suffix}",
                    value=result.get("Qi", float("inf")),
                    unit="",
                    device_type="resonator",
                    method=method_name,
                    extra=param_extra,
                )
                if "tau" in result:
                    self.param_service.create_or_update_param(
                        dataset.id,
                        name=f"electrical_delay{suffix}",
                        value=result["tau"] * 1e9,
                        unit="ns",
                        device_type="resonator",
                        method=method_name,
                        extra=param_extra,
                    )

                if model == "notch":
                    model_s21 = notch_s21(
                        f_arr,
                        fr=result["fr"],
                        Ql=result["Ql"],
                        Qc_real=result["Qc_real"],
                        Qc_imag=result["Qc_imag"],
                        a=result["a"],
                        alpha=result["alpha"],
                        tau=result["tau"],
                    )
                elif model == "transmission":
                    model_s21 = transmission_s21(
                        f_arr,
                        fr=result["fr"],
                        Ql=result["Ql"],
                        a=result["a"],
                        alpha=result["alpha"],
                        tau=result["tau"],
                    )
            elif model == "vf":
                for idx, res in enumerate(result["resonances"], start=1):
                    self.param_service.create_or_update_param(
                        dataset.id,
                        name=f"mode_{idx}_ghz{suffix}",
                        value=res["fr"] / 1e9,
                        unit="GHz",
                        device_type="resonator",
                        method=method_name,
                        extra=param_extra,
                    )
                    self.param_service.create_or_update_param(
                        dataset.id,
                        name=f"Ql_{idx}{suffix}",
                        value=res["Ql"],
                        unit="",
                        device_type="resonator",
                        method=method_name,
                        extra=param_extra,
                    )
                model_s21 = result["model_s21"]

            if l_jun_val is not None:
                self.param_service.create_or_update_param(
                    dataset.id,
                    name=f"L_jun{suffix}",
                    value=l_jun_val,
                    unit="nH",
                    device_type="resonator",
                    method=method_name,
                    extra=param_extra,
                )

            slice_results.append(
                {
                    **result,
                    "bias_index": bi,
                    "l_jun": l_jun_val,
                    "data": {
                        "f": f_arr,
                        "s21_raw": s21_arr,
                        "s21_model": model_s21,
                    },
                }
            )

        if not slice_results:
            raise ValueError("No valid bias slices found with enough data points to fit.")

        # If single slice, return flat dict for backward compatibility
        if len(slice_results) == 1:
            return slice_results[0]

        # Multiple slices — return a list under "slices" key
        return {
            "slices": slice_results,
            "l_jun_values": l_jun_values,
            "bias_indices": [s["bias_index"] for s in slice_results],
        }

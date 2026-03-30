using ProgressMeter

const PROGRESS_LOCK = ReentrantLock()
const PROGRESS_METERS = Dict{String, Progress}()

function format_progress_bar(current::Int, total::Int; width::Int=28)
    total = max(total, 1)
    ratio = clamp(current / total, 0.0, 1.0)
    filled = clamp(round(Int, ratio * width), 0, width)
    return "[" * repeat("#", filled) * repeat("-", width - filled) * "]"
end

function progress_description(label::AbstractString, detail::AbstractString="")
    return rstrip(String(label))
end

function progress_showvalues(detail::AbstractString="")
    return isempty(detail) ? () : [("detail", detail)]
end

function reset_progress!(label::AbstractString)
    lock(PROGRESS_LOCK) do
        meter = pop!(PROGRESS_METERS, String(label), nothing)
        if meter !== nothing
            ProgressMeter.finish!(meter)
        end
    end
    return nothing
end

function print_progress_update(label::AbstractString, current::Int, total::Int; detail::AbstractString="")
    safe_total = max(total, 1)
    safe_current = clamp(current, 0, safe_total)
    progress_key = rstrip(String(label))

    lock(PROGRESS_LOCK) do
        desc = progress_description(label, detail)
        showvalues = progress_showvalues(detail)
        meter = get!(PROGRESS_METERS, progress_key) do
            Progress(
                safe_total;
                desc=desc,
                dt=0.15,
                output=stderr,
                showspeed=false,
            )
        end

        if meter.n != safe_total
            meter.n = safe_total
        end

        ProgressMeter.update!(meter, safe_current; desc=desc, showvalues=showvalues)

        if safe_current >= safe_total
            ProgressMeter.finish!(meter)
            delete!(PROGRESS_METERS, progress_key)
        end
    end

    return nothing
end

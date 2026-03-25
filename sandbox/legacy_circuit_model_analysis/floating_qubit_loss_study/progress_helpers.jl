using UUIDs
using ProgressMeter

const ROOT_PROGRESS_PARENT = nothing

const PROGRESS_LOCK = ReentrantLock()
const PROGRESS_SCOPE_NAMES = Dict{UUID, String}()
const PROGRESS_METERS = Dict{UUID, Progress}()

function with_terminal_logger(f; right_justify::Int=120)
    return f()
end

function build_progress_desc(scope_name::AbstractString, detail::AbstractString="")
    return isempty(detail) ? String(scope_name) : "$(scope_name) | $(detail)"
end

function with_progress_scope(f, name::AbstractString; parentid=ROOT_PROGRESS_PARENT)
    progress_id = uuid4()
    lock(PROGRESS_LOCK) do
        PROGRESS_SCOPE_NAMES[progress_id] = String(name)
    end
    try
        return f(progress_id)
    finally
        lock(PROGRESS_LOCK) do
            meter = pop!(PROGRESS_METERS, progress_id, nothing)
            if meter !== nothing
                ProgressMeter.finish!(meter)
            end
            delete!(PROGRESS_SCOPE_NAMES, progress_id)
        end
    end
end

function update_progress!(
    progress_id,
    current::Integer,
    total::Integer;
    name::AbstractString="",
    parentid=ROOT_PROGRESS_PARENT,
)
    safe_total = max(total, 1)
    safe_current = clamp(current, 0, safe_total)
    lock(PROGRESS_LOCK) do
        scope_name = get(PROGRESS_SCOPE_NAMES, progress_id, "Progress")
        detail = String(name)
        desc = build_progress_desc(scope_name, detail)

        meter = get!(PROGRESS_METERS, progress_id) do
            Progress(
                safe_total;
                desc=desc,
                dt=0.0,
                output=stderr,
                showspeed=false,
            )
        end

        if meter.n != safe_total
            meter.n = safe_total
        end
        ProgressMeter.update!(meter, safe_current; desc=desc)
    end
    return nothing
end

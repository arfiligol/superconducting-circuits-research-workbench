using Logging
using UUIDs
using ProgressLogging
using TerminalLoggers

const ROOT_PROGRESS_PARENT = ProgressLogging.ROOTID

function with_terminal_logger(f; right_justify::Int=120)
    return with_logger(TerminalLogger(right_justify=right_justify)) do
        f()
    end
end

function with_progress_scope(f, name::AbstractString; parentid=ROOT_PROGRESS_PARENT)
    progress_id = uuid4()
    progress_name = String(name)
    @info ProgressLogging.Progress(progress_id; name=progress_name, parentid=parentid)
    try
        return f(progress_id)
    finally
        @info ProgressLogging.Progress(progress_id; name=progress_name, parentid=parentid, done=true)
    end
end

function update_progress!(
    progress_id,
    current::Integer,
    total::Integer;
    name::AbstractString,
    parentid=ROOT_PROGRESS_PARENT,
)
    safe_total = max(total, 1)
    fraction = clamp(current / safe_total, 0.0, 1.0)
    @info ProgressLogging.Progress(progress_id, fraction; name=String(name), parentid=parentid)
    return nothing
end

struct FrameworkValidationError <: Exception
    message::String
end

Base.showerror(io::IO, err::FrameworkValidationError) = print(io, err.message)

function _validation_error(message)
    throw(FrameworkValidationError(String(message)))
end

function _require(condition::Bool, message)
    condition || _validation_error(message)
    return nothing
end

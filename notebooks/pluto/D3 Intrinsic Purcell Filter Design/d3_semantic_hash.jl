# This module defines the cross-language D3 semantic-value SHA-256 framing.
# The framing is a byte contract, not JSON canonicalization: types are explicit,
# integral finite Float64 values exactly representable as Int64 normalize to the
# integer framing (including negative zero); all other finite Float64 identity
# is its exact IEEE-754 bit pattern. Strings are length-prefixed UTF-8 bytes,
# and mappings accept only sorted ASCII string keys. Raw file identity remains
# a separate byte-for-byte file SHA-256.

module D3SemanticHash

using SHA

export SEMANTIC_HASH_FRAMING, semantic_value_bytes, semantic_value_sha256

const SEMANTIC_HASH_FRAMING = "d3-semantic-value-sha256-v1"
const PREFIX = codeunits(SEMANTIC_HASH_FRAMING * "|")

function encode_value!(io, value)
    if isnothing(value)
        write(io, "n;")
    elseif value isa Bool
        write(io, value ? "b1;" : "b0;")
    elseif value isa Integer
        write(io, "i", string(value), ";")
    elseif value isa Float64
        isfinite(value) || error("D3 semantic hash rejects non-finite Float64 values.")
        normalized_integer = try
            integer = Int64(value)
            Float64(integer) == value ? integer : nothing
        catch exception
            exception isa InexactError || rethrow()
            nothing
        end
        if isnothing(normalized_integer)
            write(io, "f", lowercase(string(reinterpret(UInt64, value); base = 16, pad = 16)), ";")
        else
            write(io, "i", string(normalized_integer), ";")
        end
    elseif value isa AbstractString
        bytes = codeunits(String(value))
        write(io, "s", string(length(bytes)), ":")
        write(io, bytes)
    elseif value isa AbstractVector || value isa Tuple
        write(io, "l", string(length(value)), "[")
        for item in value
            encode_value!(io, item)
        end
        write(io, "]")
    elseif value isa AbstractDict
        keys_as_strings = String[]
        for key in keys(value)
            key isa AbstractString || error("D3 semantic hash mapping keys must be strings.")
            key_string = String(key)
            isascii(key_string) || error("D3 semantic hash mapping keys must be ASCII.")
            push!(keys_as_strings, key_string)
        end
        length(unique(keys_as_strings)) == length(keys_as_strings) || error("D3 semantic hash mapping keys must be unique.")
        sort!(keys_as_strings)
        write(io, "m", string(length(keys_as_strings)), "{")
        for key in keys_as_strings
            encode_value!(io, key)
            encode_value!(io, value[key])
        end
        write(io, "}")
    else
        error("Unsupported D3 semantic hash value type $(typeof(value)).")
    end
    return io
end

function semantic_value_bytes(value)
    io = IOBuffer()
    write(io, PREFIX)
    encode_value!(io, value)
    return take!(io)
end

semantic_value_sha256(value) = bytes2hex(SHA.sha256(semantic_value_bytes(value)))

end

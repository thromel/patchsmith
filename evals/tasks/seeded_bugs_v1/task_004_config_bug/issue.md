The default timeout setting has the wrong type.

get_default_timeout() should return the integer 30 so callers can compare and add durations without converting from text.


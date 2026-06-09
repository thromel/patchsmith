The moving_average function drops the exact-window case.

When the input length is equal to the window size, moving_average([1, 2, 3], 3) should return [2.0] instead of [].


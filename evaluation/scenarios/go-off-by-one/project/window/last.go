package window

// LastN returns the last n elements of xs, or all of xs when n >= len(xs).
func LastN(xs []int, n int) []int {
	if n >= len(xs) {
		return xs
	}
	return xs[len(xs)-n-1:]
}

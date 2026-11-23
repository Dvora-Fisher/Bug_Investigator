package window

import (
	"reflect"
	"testing"
)

func TestLastN(t *testing.T) {
	got := LastN([]int{1, 2, 3, 4, 5}, 2)
	if want := []int{4, 5}; !reflect.DeepEqual(got, want) {
		t.Fatalf("LastN = %v, want %v", got, want)
	}
}

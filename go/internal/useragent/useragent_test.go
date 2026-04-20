package useragent

import (
	"runtime"
	"strings"
	"testing"
)

func TestBuild_Shape(t *testing.T) {
	got := Build("0.1.0")
	if !strings.HasPrefix(got, "legalize-go/0.1.0 ") {
		t.Errorf("prefix: %q", got)
	}
	if !strings.Contains(got, " go/") {
		t.Errorf("missing go token: %q", got)
	}
	if !strings.HasSuffix(got, " "+runtime.GOOS) {
		t.Errorf("missing goos suffix: %q", got)
	}
}

func TestGoVersion_StripsPrefix(t *testing.T) {
	got := goVersion()
	if strings.HasPrefix(got, "go") {
		t.Errorf("should not start with 'go': %q", got)
	}
	if got == "" {
		t.Error("empty")
	}
}

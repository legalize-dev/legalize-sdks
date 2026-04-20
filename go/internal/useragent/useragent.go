// Package useragent builds the User-Agent header value every Legalize
// SDK request carries. The format matches the Python and Node SDKs:
//
//	legalize-go/<sdk-version> go/<runtime> <goos>
//
// e.g. "legalize-go/0.1.0 go/1.23.1 darwin".
package useragent

import (
	"runtime"
	"strings"
)

// Build returns the canonical User-Agent value for the SDK.
func Build(sdkVersion string) string {
	return "legalize-go/" + sdkVersion + " go/" + goVersion() + " " + runtime.GOOS
}

// goVersion returns the Go runtime version with the "go" prefix stripped
// so it pairs cleanly with the leading "go/" token.
func goVersion() string {
	v := runtime.Version()
	return strings.TrimPrefix(v, "go")
}

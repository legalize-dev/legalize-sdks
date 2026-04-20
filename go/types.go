package legalize

// String returns a pointer to s. It exists so callers can pass
// optional fields inline without a temporary variable:
//
//	opts := &legalize.LawsListOptions{ Status: legalize.String("vigente") }
func String(s string) *string { return &s }

// Int returns a pointer to n.
func Int(n int) *int { return &n }

// Bool returns a pointer to b.
func Bool(b bool) *bool { return &b }

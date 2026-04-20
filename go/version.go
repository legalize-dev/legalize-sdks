package legalize

// Version is the released SDK version. It ships in the User-Agent
// header so operators can correlate server-side metrics with a
// specific client build.
//
// Keep this in sync with the git tag (go/vX.Y.Z) when cutting a
// release. The publish workflow verifies the tag matches this value.
const Version = "0.1.0"

AWS = (
    "# AWS Keys\n\nTags: #aws #handbook\n\n## Rotation\n\n"
    "Rotate AWS access keys every ninety days and delete the old ones. Long-lived "
    "credentials are a security risk, so rotation is mandatory for every service account.\n"
)
CAKE = (
    "# Cake\n\nTags: #food #handbook\n\n## Recipe\n\n"
    "Mix flour, eggs and sugar, then bake the chocolate cake for forty minutes. Let it "
    "cool on a rack before adding the frosting, otherwise the frosting melts.\n"
)


def numbered(n: int) -> str:
    """A note on key rotation with its own title."""
    return AWS.replace("AWS Keys", f"Note {n}")

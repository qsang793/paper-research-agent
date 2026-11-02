export function buildBackendHeaders(
    internalToken: string | undefined = process.env.BACKEND_INTERNAL_TOKEN
): Record<string, string> {
    if (!internalToken) {
        throw new Error("BACKEND_INTERNAL_TOKEN is not configured");
    }
    return {
        "Content-Type": "application/json",
        "X-Internal-Token": internalToken,
    };
}

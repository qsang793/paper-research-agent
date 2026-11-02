const STORAGE_KEY = "research-chat-session-id";

type StringStorage = Pick<Storage, "getItem" | "setItem">;

// localStorage can throw (private browsing, blocked cookies) or be unavailable during SSR.
// Callers should always go through this instead of touching window.localStorage directly.
export function getBrowserSessionStorage(): StringStorage | null {
    if (typeof window === "undefined") {
        return null;
    }
    try {
        return window.localStorage;
    } catch {
        return null;
    }
}

function generateChatSessionId(): string {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
        return crypto.randomUUID();
    }
    return `chat-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function getOrCreateChatSessionId(storage: StringStorage | null): string {
    const existing = storage?.getItem(STORAGE_KEY);
    if (existing) {
        return existing;
    }
    const created = generateChatSessionId();
    storage?.setItem(STORAGE_KEY, created);
    return created;
}

export function rotateChatSessionId(storage: StringStorage | null): string {
    const created = generateChatSessionId();
    storage?.setItem(STORAGE_KEY, created);
    return created;
}

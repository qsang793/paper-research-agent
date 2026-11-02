function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null;
}

export type ParsedChatRequestBody =
    | { ok: true; lastMessage: unknown; body: Record<string, unknown> }
    | { ok: false; error: string };

export function getAuthenticatedUserId(session: unknown): string | null {
    if (!isRecord(session) || !isRecord(session.user)) return null;
    return typeof session.user.id === "string" && session.user.id.length > 0
        ? session.user.id
        : null;
}

export function parseChatRequestBody(requestBody: unknown): ParsedChatRequestBody {
    if (!isRecord(requestBody) || Array.isArray(requestBody)) {
        return { ok: false, error: "Invalid request body" };
    }

    const { messages, ...body } = requestBody;
    if (!Array.isArray(messages) || messages.length === 0) {
        return {
            ok: false,
            error: "Request body must include at least one message",
        };
    }

    return {
        ok: true,
        lastMessage: messages[messages.length - 1],
        body,
    };
}

export function getMessageText(message: unknown): string {
    if (!isRecord(message)) return "";
    if (typeof message?.content === "string") return message.content;
    if (Array.isArray(message?.parts)) {
        return message.parts
            .filter((part) => isRecord(part) && part.type === "text")
            .map((part) => (typeof part.text === "string" ? part.text : ""))
            .join("");
    }
    return "";
}

export function buildBackendChatRequestBody(
    lastMessage: unknown,
    body: Record<string, unknown>
): Record<string, unknown> {
    return {
        query: getMessageText(lastMessage),
        ...body,
    };
}

export function attachServerUserId(
    body: Record<string, unknown>,
    userId: string | null | undefined
): Record<string, unknown> {
    const rest = { ...body };
    delete rest.user_id;
    if (!userId) {
        return rest;
    }
    return {
        ...rest,
        user_id: userId,
    };
}

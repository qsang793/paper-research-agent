import test from "node:test";
import assert from "node:assert/strict";

import {
    attachServerUserId,
    buildBackendChatRequestBody,
    getAuthenticatedUserId,
    getMessageText,
    parseChatRequestBody,
} from "./route-helpers.ts";

test("getMessageText returns string content", () => {
    assert.equal(getMessageText({ content: "What is RAG?" }), "What is RAG?");
});

test("getMessageText joins text parts and ignores non-text parts", () => {
    assert.equal(
        getMessageText({
            parts: [
                { type: "text", text: "hello " },
                { type: "source-url", url: "https://example.com" },
                { type: "text", text: "world" },
            ],
        }),
        "hello world"
    );
});

test("buildBackendChatRequestBody preserves session_id from request body", () => {
    assert.deepEqual(
        buildBackendChatRequestBody(
            { content: "What is RAG?" },
            {
                session_id: "chat-abc",
                mode: "auto",
            }
        ),
        {
            query: "What is RAG?",
            session_id: "chat-abc",
            mode: "auto",
        }
    );
});

test("parseChatRequestBody returns the last message and remaining body", () => {
    assert.deepEqual(
        parseChatRequestBody({
            messages: [
                { content: "first" },
                { content: "second" },
            ],
            session_id: "chat-abc",
            mode: "auto",
        }),
        {
            ok: true,
            lastMessage: { content: "second" },
            body: {
                session_id: "chat-abc",
                mode: "auto",
            },
        }
    );
});

test("parseChatRequestBody rejects invalid or empty message payloads", () => {
    assert.deepEqual(
        parseChatRequestBody(null),
        { ok: false, error: "Invalid request body" }
    );
    assert.deepEqual(
        parseChatRequestBody([]),
        { ok: false, error: "Invalid request body" }
    );
    assert.deepEqual(
        parseChatRequestBody({}),
        {
            ok: false,
            error: "Request body must include at least one message",
        }
    );
    assert.deepEqual(
        parseChatRequestBody({ messages: [] }),
        {
            ok: false,
            error: "Request body must include at least one message",
        }
    );
});

test("attachServerUserId overwrites client-supplied user_id with authenticated user id", () => {
    assert.deepEqual(
        attachServerUserId(
            {
                user_id: "spoofed-user-id",
                session_id: "chat-session-1",
                mode: "auto",
            },
            "server-user-42"
        ),
        {
            session_id: "chat-session-1",
            mode: "auto",
            user_id: "server-user-42",
        }
    );
});

test("attachServerUserId strips client-supplied user_id when no server user exists", () => {
    assert.deepEqual(
        attachServerUserId(
            {
                user_id: "spoofed-user-id",
                session_id: "chat-session-2",
                mode: "auto",
            },
            undefined
        ),
        {
            session_id: "chat-session-2",
            mode: "auto",
        }
    );
});

test("attachServerUserId strips client-supplied user_id for null or empty user id", () => {
    assert.deepEqual(
        attachServerUserId(
            {
                user_id: "spoofed-user-id",
                session_id: "chat-session-3",
                mode: "auto",
            },
            null
        ),
        {
            session_id: "chat-session-3",
            mode: "auto",
        }
    );

    assert.deepEqual(
        attachServerUserId(
            {
                user_id: "spoofed-user-id",
                session_id: "chat-session-4",
                mode: "auto",
            },
            ""
        ),
        {
            session_id: "chat-session-4",
            mode: "auto",
        }
    );
});

test("getAuthenticatedUserId accepts only a non-empty server session id", () => {
    assert.equal(getAuthenticatedUserId({ user: { id: "github:123" } }), "github:123");
    assert.equal(getAuthenticatedUserId({ user: { id: "" } }), null);
    assert.equal(getAuthenticatedUserId({ user: {} }), null);
    assert.equal(getAuthenticatedUserId(null), null);
});

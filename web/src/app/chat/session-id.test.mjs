import test from "node:test";
import assert from "node:assert/strict";

import { getBrowserSessionStorage, getOrCreateChatSessionId, rotateChatSessionId } from "./session-id.ts";

function fakeStorage(initial = {}) {
    const data = { ...initial };
    return {
        getItem: (key) => (key in data ? data[key] : null),
        setItem: (key, value) => {
            data[key] = value;
        },
        dump: () => ({ ...data }),
    };
}

test("getOrCreateChatSessionId returns the stored id when present", () => {
    const storage = fakeStorage({ "research-chat-session-id": "existing-id" });
    assert.equal(getOrCreateChatSessionId(storage), "existing-id");
});

test("getOrCreateChatSessionId creates and persists a new id when absent", () => {
    const storage = fakeStorage();
    const id = getOrCreateChatSessionId(storage);
    assert.ok(id.length > 0);
    assert.equal(storage.dump()["research-chat-session-id"], id);
    assert.equal(getOrCreateChatSessionId(storage), id);
});

test("rotateChatSessionId always issues and persists a fresh id", () => {
    const storage = fakeStorage({ "research-chat-session-id": "old-id" });
    const next = rotateChatSessionId(storage);
    assert.notEqual(next, "old-id");
    assert.equal(storage.dump()["research-chat-session-id"], next);
});

test("helpers tolerate a null storage (SSR)", () => {
    const created = getOrCreateChatSessionId(null);
    assert.ok(created.length > 0);
    assert.ok(rotateChatSessionId(null).length > 0);
});

test("getBrowserSessionStorage returns null without a window (SSR/node), and helpers still work with it", () => {
    assert.equal(typeof window, "undefined");
    const storage = getBrowserSessionStorage();
    assert.equal(storage, null);
    assert.ok(getOrCreateChatSessionId(storage).length > 0);
    assert.ok(rotateChatSessionId(storage).length > 0);
});

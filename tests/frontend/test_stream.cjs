const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const inertElement = { addEventListener() {}, focus() {} };
const context = vm.createContext({
    document: {
        getElementById() { return inertElement; },
        querySelectorAll() { return []; },
        addEventListener() {}
    },
    window: {},
    TextDecoder
});
const source = fs.readFileSync(
    path.join(__dirname, "../../frontend/app.js"), "utf8"
);
vm.runInContext(source, context);

function mockResponse(parts) {
    const encoder = new TextEncoder();
    const chunks = parts.map((part) => encoder.encode(part));
    let released = false;
    return {
        body: {
            getReader() {
                return {
                    async read() {
                        return chunks.length
                            ? { value: chunks.shift(), done: false }
                            : { done: true };
                    },
                    releaseLock() { released = true; }
                };
            }
        },
        get released() { return released; }
    };
}

test("parses NDJSON across arbitrary network chunk boundaries", async () => {
    const response = mockResponse([
        '{"type":"sta',
        'ge","stage":"retrieving"}\n{"type":"draft","text":"S',
        'afeguard"}\n{"type":"complete","result":{}}\n'
    ]);
    const events = [];
    await context.readEventStream(response, (event) => events.push(event));
    assert.deepEqual(events.map((event) => event.type), [
        "stage", "draft", "complete"
    ]);
    assert.equal(events[1].text, "Safeguard");
    assert.equal(response.released, true);
});

test("rejects a stream cut off before a checked completion", async () => {
    const response = mockResponse(['{"type":"draft","text":"Unverified"}\n']);
    await assert.rejects(
        context.readEventStream(response, () => {}),
        /ended before completion/
    );
    assert.equal(response.released, true);
});

test("rejects events after the terminal completion", async () => {
    const response = mockResponse([
        '{"type":"complete","result":{}}\n{"type":"draft","text":"late"}\n'
    ]);
    await assert.rejects(
        context.readEventStream(response, () => {}),
        /after completion/
    );
    assert.equal(response.released, true);
});

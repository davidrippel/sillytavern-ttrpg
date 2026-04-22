export function parseYaml(text) {
    const parser = globalThis.SillyTavern?.libs?.yaml;

    if (!parser || typeof parser.parse !== 'function') {
        throw new Error('SillyTavern YAML parser is unavailable.');
    }

    return parser.parse(text);
}

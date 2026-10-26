/**
 * The production bundle must call the deployed API, not a relative path.
 *
 * In production the frontend is served from Netlify while the API lives on
 * Render, so every request needs the absolute base URL from
 * `VITE_API_BASE_URL`. Local development falls back to the relative `/api/v1`
 * that the Vite dev proxy forwards to 127.0.0.1:8000.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const client = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8');

test('the API base URL is read from VITE_API_BASE_URL', () => {
  assert.match(client, /import\.meta\.env\.VITE_API_BASE_URL/);
});

test('local development falls back to the relative /api/v1 path', () => {
  assert.match(client, /VITE_API_BASE_URL\s*\?\?\s*'\/api\/v1'/);
});

test('every request goes through one base-prefixed fetch', () => {
  assert.equal(client.match(/\bfetch\(/g).length, 1);
  assert.match(client, /fetch\(`\$\{API_BASE\}\$\{path\}`/);
});

test('the base URL never repeats the /api/v1 segment', () => {
  assert.doesNotMatch(client, /API_BASE\s*=\s*[^;]*\/api\/v1[^;]*\/api\/v1/);
});

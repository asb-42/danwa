/**
 * Unit Tests — workflowExec.js phase-snapshot helpers
 *
 * Validates URL construction, URL-encoding, and the 404 -> null
 * fallback for `getPhaseSnapshotDetail()`.
 *
 * `workflowExec.js` calls `request()` from `./api.js` (re-exported
 * from `./api/core.js`).  We mock that import so the tests do not
 * touch the network.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('../../../src/lib/api.js', () => ({
  request: vi.fn(),
}));

import { request } from '../../../src/lib/api.js';
import {
  getPhaseSnapshots,
  getPhaseSnapshotDetail,
} from '../../../src/lib/workflowExec.js';

const SID = 'session with spaces'; // also covers URL-encoding
const NID = 'node/gate-1';

beforeEach(() => {
  vi.resetAllMocks();
});

describe('getPhaseSnapshots()', () => {
  it('hits the /phase-snapshots endpoint with URL-encoded sessionId', async () => {
    request.mockResolvedValueOnce([{ node_id: NID }]);
    const result = await getPhaseSnapshots(SID);
    expect(request).toHaveBeenCalledTimes(1);
    expect(request).toHaveBeenCalledWith(
      `/api/v1/workflow-exec/${encodeURIComponent(SID)}/phase-snapshots`,
    );
    expect(result).toEqual([{ node_id: NID }]);
  });

  it('propagates errors from request()', async () => {
    request.mockRejectedValueOnce(new Error('network down'));
    await expect(getPhaseSnapshots(SID)).rejects.toThrow('network down');
  });
});

describe('getPhaseSnapshotDetail()', () => {
  it('hits the /phase-snapshots/{node_id} endpoint with both IDs encoded', async () => {
    request.mockResolvedValueOnce({ node_id: NID, state: { x: 1 } });
    const result = await getPhaseSnapshotDetail(SID, NID);
    expect(request).toHaveBeenCalledTimes(1);
    expect(request).toHaveBeenCalledWith(
      `/api/v1/workflow-exec/${encodeURIComponent(SID)}/phase-snapshots/${encodeURIComponent(NID)}`,
    );
    expect(result).toEqual({ node_id: NID, state: { x: 1 } });
  });

  it('returns null when the error message looks like a 404', async () => {
    request.mockRejectedValueOnce(new Error('HTTP 404'));
    const result = await getPhaseSnapshotDetail(SID, NID);
    expect(result).toBeNull();
  });

  it('returns null on a "not found" style error', async () => {
    request.mockRejectedValueOnce(new Error('Snapshot not found'));
    const result = await getPhaseSnapshotDetail(SID, NID);
    expect(result).toBeNull();
  });

  it('rethrows non-404 errors', async () => {
    request.mockRejectedValueOnce(new Error('HTTP 500'));
    await expect(getPhaseSnapshotDetail(SID, NID)).rejects.toThrow('HTTP 500');
  });

  it('rethrows when the error has no message', async () => {
    // Some non-Error rejects (e.g. throwing a string) should propagate.
    request.mockRejectedValueOnce('weird failure');
    await expect(getPhaseSnapshotDetail(SID, NID)).rejects.toBe('weird failure');
  });
});

/**
 * Backup management API functions (Sprint 18).
 */

import { request } from './core.js';

/** Create a new backup archive. */
export function createBackup(trigger = "manual") {
  return request("/api/v1/config/backup", { method: "POST", body: JSON.stringify({ trigger }) });
}

/** Get list of all available backups with metadata. */
export function getBackups() {
  return request("/api/v1/config/backups");
}

/** Get metadata for a specific backup. */
export function getBackup(backupId) {
  return request(`/api/v1/config/backups/${backupId}`);
}

/** Get the list of files contained in a backup. */
export function getBackupFiles(backupId) {
  return request(`/api/v1/config/backups/${backupId}/files`);
}

/** Verify the integrity of a backup. */
export function verifyBackup(backupId) {
  return request(`/api/v1/config/backups/${backupId}/verify`, { method: "POST" });
}

/**
 * Restore data from a backup.
 * ⚠️ Destructive — will overwrite existing data.
 */
export function restoreBackup(backupId) {
  return request(`/api/v1/config/backups/${backupId}/restore`, { method: "POST" });
}

/** Get current backup settings. */
export function getBackupSettings() {
  return request("/api/v1/config/backup-settings");
}

/** Update backup settings. */
export function updateBackupSettings(settings) {
  return request("/api/v1/config/backup-settings", {
    method: "PUT",
    body: JSON.stringify(settings),
  });
}

/** Delete a backup archive. */
export function deleteBackup(backupId) {
  return request(`/api/v1/config/backups/${backupId}`, { method: "DELETE" });
}

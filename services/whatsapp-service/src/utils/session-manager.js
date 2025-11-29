import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import logger from './logger.js';

class SessionManager {
    constructor(sessionName = 'bot-session') {
        this.sessionName = sessionName;
        this.sessionDir = path.join(process.cwd(), 'sessions');
        this.sessionPath = path.join(this.sessionDir, sessionName);
        this.backupDir = path.join(this.sessionDir, 'backups');
        this.maxBackups = 5;
        
        this.ensureDirectories();
    }

    ensureDirectories() {
        try {
            if (!fs.existsSync(this.sessionDir)) {
                fs.mkdirSync(this.sessionDir, { recursive: true });
                logger.info('Created sessions directory', {
                    path: this.sessionDir
                });
            }
            
            if (!fs.existsSync(this.backupDir)) {
                fs.mkdirSync(this.backupDir, { recursive: true });
                logger.info('Created session backups directory', {
                    path: this.backupDir
                });
            }
        } catch (error) {
            logger.error('Failed to create session directories:', error);
            throw error;
        }
    }

    /**
     * Check if session exists and is valid
     */
    sessionExists() {
        try {
            return fs.existsSync(this.sessionPath) && this.isValidSession();
        } catch (error) {
            logger.error('Error checking session existence:', error);
            return false;
        }
    }

    /**
     * Validate session integrity
     */
    isValidSession() {
        try {
            if (!fs.existsSync(this.sessionPath)) {
                return false;
            }

            const stats = fs.statSync(this.sessionPath);
            if (!stats.isDirectory()) {
                logger.warn('Session path exists but is not a directory', {
                    path: this.sessionPath
                });
                return false;
            }

            // Check for required session files
            const requiredFiles = ['creds.json'];
            const optionalFiles = ['app-state-sync-version.json', 'app-state-sync-key.json'];
            
            let hasRequiredFiles = true;
            for (const file of requiredFiles) {
                const filePath = path.join(this.sessionPath, file);
                if (!fs.existsSync(filePath)) {
                    logger.warn('Missing required session file', {
                        file,
                        path: filePath
                    });
                    hasRequiredFiles = false;
                }
            }

            if (!hasRequiredFiles) {
                return false;
            }

            // Validate creds.json structure
            const credsPath = path.join(this.sessionPath, 'creds.json');
            try {
                const credsContent = fs.readFileSync(credsPath, 'utf8');
                const creds = JSON.parse(credsContent);
                
                // Basic validation of credentials structure
                if (!creds.noiseKey || !creds.signedIdentityKey || !creds.signedPreKey) {
                    logger.warn('Invalid credentials structure in session');
                    return false;
                }
                
                logger.info('Session validation passed', {
                    session_name: this.sessionName,
                    has_optional_files: optionalFiles.some(file => 
                        fs.existsSync(path.join(this.sessionPath, file))
                    )
                });
                
                return true;
                
            } catch (error) {
                logger.error('Failed to validate credentials file:', error);
                return false;
            }

        } catch (error) {
            logger.error('Error validating session:', error);
            return false;
        }
    }

    /**
     * Get session information
     */
    getSessionInfo() {
        try {
            if (!this.sessionExists()) {
                return {
                    exists: false,
                    valid: false,
                    session_name: this.sessionName,
                    session_path: this.sessionPath
                };
            }

            const stats = fs.statSync(this.sessionPath);
            const files = fs.readdirSync(this.sessionPath);
            
            let totalSize = 0;
            const fileDetails = [];
            
            for (const file of files) {
                const filePath = path.join(this.sessionPath, file);
                const fileStats = fs.statSync(filePath);
                totalSize += fileStats.size;
                
                fileDetails.push({
                    name: file,
                    size: fileStats.size,
                    modified: fileStats.mtime.toISOString()
                });
            }

            return {
                exists: true,
                valid: this.isValidSession(),
                session_name: this.sessionName,
                session_path: this.sessionPath,
                created: stats.birthtime.toISOString(),
                modified: stats.mtime.toISOString(),
                total_size: totalSize,
                file_count: files.length,
                files: fileDetails,
                backups_available: this.getAvailableBackups().length
            };

        } catch (error) {
            logger.error('Error getting session info:', error);
            return {
                exists: false,
                valid: false,
                error: error.message,
                session_name: this.sessionName,
                session_path: this.sessionPath
            };
        }
    }

    /**
     * Create backup of current session
     */
    createBackup(reason = 'manual') {
        try {
            if (!this.sessionExists()) {
                throw new Error('No session to backup');
            }

            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            const backupName = `${this.sessionName}_${timestamp}_${reason}`;
            const backupPath = path.join(this.backupDir, backupName);

            // Copy session directory to backup
            this.copyDirectory(this.sessionPath, backupPath);

            // Create backup metadata
            const metadata = {
                session_name: this.sessionName,
                backup_name: backupName,
                created: new Date().toISOString(),
                reason,
                original_path: this.sessionPath,
                backup_path: backupPath,
                checksum: this.calculateDirectoryChecksum(backupPath)
            };

            const metadataPath = path.join(backupPath, '.backup-metadata.json');
            fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2));

            logger.info('Session backup created', {
                backup_name: backupName,
                backup_path: backupPath,
                reason
            });

            // Clean up old backups
            this.cleanupOldBackups();

            return {
                success: true,
                backup_name: backupName,
                backup_path: backupPath,
                metadata
            };

        } catch (error) {
            logger.error('Failed to create session backup:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Restore session from backup
     */
    restoreFromBackup(backupName) {
        try {
            const backupPath = path.join(this.backupDir, backupName);
            
            if (!fs.existsSync(backupPath)) {
                throw new Error(`Backup not found: ${backupName}`);
            }

            // Validate backup integrity
            const metadataPath = path.join(backupPath, '.backup-metadata.json');
            if (fs.existsSync(metadataPath)) {
                const metadata = JSON.parse(fs.readFileSync(metadataPath, 'utf8'));
                const currentChecksum = this.calculateDirectoryChecksum(backupPath);
                
                if (metadata.checksum !== currentChecksum) {
                    logger.warn('Backup checksum mismatch, backup may be corrupted', {
                        backup_name: backupName,
                        expected: metadata.checksum,
                        actual: currentChecksum
                    });
                }
            }

            // Create backup of current session before restore
            if (this.sessionExists()) {
                this.createBackup('pre_restore');
            }

            // Remove current session
            if (fs.existsSync(this.sessionPath)) {
                fs.rmSync(this.sessionPath, { recursive: true, force: true });
            }

            // Copy backup to session directory (excluding metadata)
            this.copyDirectory(backupPath, this.sessionPath, ['.backup-metadata.json']);

            logger.info('Session restored from backup', {
                backup_name: backupName,
                session_path: this.sessionPath
            });

            return {
                success: true,
                backup_name: backupName,
                restored_to: this.sessionPath
            };

        } catch (error) {
            logger.error('Failed to restore session from backup:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Get list of available backups
     */
    getAvailableBackups() {
        try {
            if (!fs.existsSync(this.backupDir)) {
                return [];
            }

            const backups = [];
            const items = fs.readdirSync(this.backupDir);

            for (const item of items) {
                const itemPath = path.join(this.backupDir, item);
                const stats = fs.statSync(itemPath);
                
                if (stats.isDirectory() && item.startsWith(this.sessionName)) {
                    const metadataPath = path.join(itemPath, '.backup-metadata.json');
                    let metadata = null;
                    
                    if (fs.existsSync(metadataPath)) {
                        try {
                            metadata = JSON.parse(fs.readFileSync(metadataPath, 'utf8'));
                        } catch (error) {
                            logger.warn('Failed to read backup metadata', {
                                backup: item,
                                error: error.message
                            });
                        }
                    }

                    backups.push({
                        name: item,
                        path: itemPath,
                        created: stats.birthtime.toISOString(),
                        size: this.getDirectorySize(itemPath),
                        metadata
                    });
                }
            }

            // Sort by creation date (newest first)
            backups.sort((a, b) => new Date(b.created) - new Date(a.created));

            return backups;

        } catch (error) {
            logger.error('Error getting available backups:', error);
            return [];
        }
    }

    /**
     * Clean up old backups (keep only maxBackups)
     */
    cleanupOldBackups() {
        try {
            const backups = this.getAvailableBackups();
            
            if (backups.length <= this.maxBackups) {
                return;
            }

            const backupsToDelete = backups.slice(this.maxBackups);
            
            for (const backup of backupsToDelete) {
                fs.rmSync(backup.path, { recursive: true, force: true });
                logger.info('Deleted old backup', {
                    backup_name: backup.name,
                    created: backup.created
                });
            }

        } catch (error) {
            logger.error('Error cleaning up old backups:', error);
        }
    }

    /**
     * Copy directory recursively
     */
    copyDirectory(src, dest, excludeFiles = []) {
        if (!fs.existsSync(dest)) {
            fs.mkdirSync(dest, { recursive: true });
        }

        const items = fs.readdirSync(src);

        for (const item of items) {
            if (excludeFiles.includes(item)) {
                continue;
            }

            const srcPath = path.join(src, item);
            const destPath = path.join(dest, item);
            const stats = fs.statSync(srcPath);

            if (stats.isDirectory()) {
                this.copyDirectory(srcPath, destPath, excludeFiles);
            } else {
                fs.copyFileSync(srcPath, destPath);
            }
        }
    }

    /**
     * Calculate directory checksum for integrity verification
     */
    calculateDirectoryChecksum(dirPath) {
        try {
            const hash = crypto.createHash('sha256');
            const files = this.getAllFiles(dirPath).sort();

            for (const file of files) {
                const relativePath = path.relative(dirPath, file);
                const content = fs.readFileSync(file);
                hash.update(relativePath);
                hash.update(content);
            }

            return hash.digest('hex');

        } catch (error) {
            logger.error('Error calculating directory checksum:', error);
            return null;
        }
    }

    /**
     * Get all files in directory recursively
     */
    getAllFiles(dirPath) {
        const files = [];
        const items = fs.readdirSync(dirPath);

        for (const item of items) {
            const itemPath = path.join(dirPath, item);
            const stats = fs.statSync(itemPath);

            if (stats.isDirectory()) {
                files.push(...this.getAllFiles(itemPath));
            } else {
                files.push(itemPath);
            }
        }

        return files;
    }

    /**
     * Get directory size in bytes
     */
    getDirectorySize(dirPath) {
        try {
            let totalSize = 0;
            const files = this.getAllFiles(dirPath);

            for (const file of files) {
                const stats = fs.statSync(file);
                totalSize += stats.size;
            }

            return totalSize;

        } catch (error) {
            logger.error('Error calculating directory size:', error);
            return 0;
        }
    }

    /**
     * Validate session and create backup if needed
     */
    validateAndBackup() {
        try {
            if (!this.sessionExists()) {
                logger.info('No session found, nothing to validate');
                return {
                    session_exists: false,
                    valid: false,
                    backup_created: false
                };
            }

            const isValid = this.isValidSession();
            let backupResult = null;

            if (isValid) {
                // Create backup of valid session
                backupResult = this.createBackup('validation');
                logger.info('Session validation passed, backup created');
            } else {
                logger.warn('Session validation failed');
            }

            return {
                session_exists: true,
                valid: isValid,
                backup_created: backupResult?.success || false,
                backup_info: backupResult
            };

        } catch (error) {
            logger.error('Error during session validation and backup:', error);
            return {
                session_exists: false,
                valid: false,
                backup_created: false,
                error: error.message
            };
        }
    }
}

export default SessionManager;
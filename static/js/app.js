// Schemini Manager Web Application JavaScript

// Global variables
let currentOperation = null;
let progressInterval = null;
let logInterval = null;

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    // Initialize and show toasts for flash messages
    const toastContainer = document.getElementById('toastContainer');
    if (toastContainer) {
        const toastElements = toastContainer.querySelectorAll('.toast');
        toastElements.forEach(toastEl => {
            const toast = new bootstrap.Toast(toastEl, {
                delay: 5000 // Show for 5 seconds
            });
            toast.show();
        });
    }

    // Add a global event listener for reference folder changes
    const referenceFolderInput = document.getElementById('referenceFolder');
    if (referenceFolderInput) {
        // This input is readonly, so we cant listen for user input.
        // Instead, other parts of the code should call the update function
        // when they programmatically change the folder.
        // We will expose a function for this.
    }

    initializeApp();
});

function initializeApp() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Setup error handling
    setupErrorHandling();
}

function setupErrorHandling() {
    window.addEventListener('error', function(event) {
        console.error('JavaScript Error:', event.error);
        showNotification('An unexpected error occurred', 'error');
    });

    window.addEventListener('unhandledrejection', function(event) {
        console.error('Unhandled Promise Rejection:', event.reason);
        showNotification('A network error occurred', 'error');
    });
}

// Notification system
function showNotification(message, type = 'info', duration = 5000) {
    const notification = document.createElement('div');
    notification.className = `alert alert-dismissible fade show position-fixed shadow-lg`;
    
    // Color scheme for better visibility
    const colorSchemes = {
        'success': {
            bg: '#d1edcc',
            text: '#0f5132',
            border: '#badbcc'
        },
        'error': {
            bg: '#f8d7da',
            text: '#721c24',
            border: '#f5c6cb'
        },
        'warning': {
            bg: '#fff3cd',
            text: '#856404',
            border: '#ffeaa7'
        },
        'info': {
            bg: '#d1ecf1',
            text: '#0c5460',
            border: '#bee5eb'
        }
    };
    
    const scheme = colorSchemes[type] || colorSchemes['info'];
    
    notification.style.cssText = `
        top: 80px;
        right: 20px;
        z-index: 1060;
        min-width: 320px;
        max-width: 500px;
        background-color: ${scheme.bg};
        color: ${scheme.text};
        border: 1px solid ${scheme.border};
        border-radius: 8px;
        font-weight: 500;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    `;
    
    const iconMap = {
        'success': 'check-circle-fill',
        'error': 'exclamation-triangle-fill',
        'warning': 'exclamation-triangle-fill',
        'info': 'info-circle-fill'
    };
    
    notification.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="bi bi-${iconMap[type]} me-2 fs-5"></i>
            <span class="flex-grow-1">${message}</span>
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close" style="color: ${scheme.text};"></button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Auto remove after duration
    setTimeout(() => {
        if (notification.parentNode) {
            notification.classList.remove('show');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 150);
        }
    }, duration);
}

// Loading state management
function setLoadingState(element, isLoading) {
    if (isLoading) {
        element.classList.add('loading');
        if (element.tagName === 'BUTTON') {
            element.disabled = true;
            element.dataset.originalText = element.innerHTML;
            element.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';
        }
    } else {
        element.classList.remove('loading');
        if (element.tagName === 'BUTTON') {
            element.disabled = false;
            if (element.dataset.originalText) {
                element.innerHTML = element.dataset.originalText;
                delete element.dataset.originalText;
            }
        }
    }
}

// Progress monitoring
function startProgressMonitoring(operationType, progressElementId, statusElementId) {
    currentOperation = operationType;
    
    progressInterval = setInterval(() => {
        fetch(`/api/get-progress/${operationType}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateProgressDisplay(data.progress, progressElementId, statusElementId);
                    
                    if (data.progress.completed || data.progress.error) {
                        stopProgressMonitoring();
                        handleOperationComplete(data.progress);
                    }
                } else {
                    console.error('Progress fetch error:', data.message);
                }
            })
            .catch(error => {
                console.error('Progress monitoring error:', error);
            });
    }, 1000);
}

function stopProgressMonitoring() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
    currentOperation = null;
}

function updateProgressDisplay(progress, progressElementId, statusElementId) {
    const progressElement = document.getElementById(progressElementId);
    const statusElement = document.getElementById(statusElementId);
    
    if (progressElement) {
        progressElement.style.width = `${progress.percentage}%`;
        progressElement.textContent = `${Math.round(progress.percentage)}%`;
    }
    
    if (statusElement) {
        statusElement.textContent = progress.status || 'Processing...';
    }
}

function handleOperationComplete(progress) {
    if (progress.error) {
        showNotification(`Operation failed: ${progress.error}`, 'error');
    } else {
        showNotification('Operation completed successfully!', 'success');
    }
}

// Log monitoring
function startLogMonitoring(operationType, logElementId) {
    logInterval = setInterval(() => {
        fetch(`/api/get-logs/${operationType}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateLogDisplay(data.logs, logElementId);
                }
            })
            .catch(error => {
                console.error('Log monitoring error:', error);
            });
    }, 2000);
}

function stopLogMonitoring() {
    if (logInterval) {
        clearInterval(logInterval);
        logInterval = null;
    }
}

function updateLogDisplay(logs, logElementId) {
    const logElement = document.getElementById(logElementId);
    if (!logElement) return;
    
    // Clear and rebuild log display
    logElement.innerHTML = '';
    
    logs.forEach(log => {
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        logEntry.textContent = log;
        
        // Add color coding based on log content
        if (log.includes('✅') || log.includes('SUCCESS')) {
            logEntry.style.color = '#28a745';
        } else if (log.includes('❌') || log.includes('ERROR')) {
            logEntry.style.color = '#dc3545';
        } else if (log.includes('⚠️') || log.includes('WARNING')) {
            logEntry.style.color = '#ffc107';
        } else if (log.includes('ℹ️') || log.includes('INFO')) {
            logEntry.style.color = '#17a2b8';
        }
        
        logElement.appendChild(logEntry);
    });
    
    // Auto scroll to bottom
    logElement.scrollTop = logElement.scrollHeight;
}

// File operations
async function selectFolder(inputElementId, title = 'Select Folder') {
    try {
        // For web browsers, we'll provide two options:
        // 1. Manual path entry (most reliable for exact paths)
        // 2. File-based folder detection (as fallback)
        
        const inputElement = document.getElementById(inputElementId);
        if (!inputElement) {
            console.error('Input element not found:', inputElementId);
            return null;
        }

        // First, try to get a manual path entry
        const manualPath = prompt(`${title}:\n\nEnter the exact folder path you want to use:\n(e.g., C:\\Users\\YourName\\SCHEMINI4)`);
        
        if (manualPath && manualPath.trim()) {
            const cleanPath = manualPath.trim();
            inputElement.value = cleanPath;
            
            // Trigger change event
            const changeEvent = new Event('change', { bubbles: true });
            inputElement.dispatchEvent(changeEvent);
            
            return cleanPath;
        }
        
        // If manual entry was cancelled, try the file-based approach as fallback
        const input = document.createElement('input');
        input.type = 'file';
        input.webkitdirectory = true;
        input.style.display = 'none';
        
        return new Promise((resolve) => {
            input.addEventListener('change', function(event) {
                const files = event.target.files;
                if (files.length > 0) {
                    // Try to get the root folder path more intelligently
                    const firstFile = files[0];
                    const fullPath = firstFile.webkitRelativePath;
                    
                    // Extract just the top-level folder name
                    const topFolder = fullPath.split('/')[0];
                    
                    // For better path handling, let user confirm the detected path
                    const detectedPath = prompt(
                        `Detected folder: ${topFolder}\n\n` +
                        `If this is not the correct path, please enter the full path manually:\n` +
                        `(Cancel to use detected path)`
                    );
                    
                    const finalPath = detectedPath && detectedPath.trim() ? detectedPath.trim() : topFolder;
                    
                    inputElement.value = finalPath;
                    
                    // Trigger change event
                    const changeEvent = new Event('change', { bubbles: true });
                    inputElement.dispatchEvent(changeEvent);
                    
                    resolve(finalPath);
                }
                document.body.removeChild(input);
            });
            
            input.addEventListener('cancel', function() {
                document.body.removeChild(input);
                resolve(null);
            });
            
            document.body.appendChild(input);
            input.click();
        });
    } catch (error) {
        console.error('Folder selection error:', error);
        // Final fallback to simple prompt
        const folder = prompt(`${title}:\nEnter folder path:`);
        if (folder) {
            const inputElement = document.getElementById(inputElementId);
            if (inputElement) {
                inputElement.value = folder.trim();
                const event = new Event('change', { bubbles: true });
                inputElement.dispatchEvent(event);
            }
            return folder.trim();
        }
        return null;
    }
}

function validateFolderPath(path) {
    // Basic validation
    if (!path || path.trim() === '') {
        return false;
    }
    
    // Check for common invalid characters (this is a basic check)
    const invalidChars = /[<>:"|?*]/;
    return !invalidChars.test(path);
}

// Form validation
function validateForm(formId, requiredFields) {
    const form = document.getElementById(formId);
    if (!form) return false;
    
    let isValid = true;
    const errors = [];
    
    requiredFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (!field) return;
        
        const value = field.value.trim();
        
        // Remove previous error styling
        field.classList.remove('is-invalid');
        
        if (!value) {
            isValid = false;
            field.classList.add('is-invalid');
            errors.push(`${field.previousElementSibling?.textContent || fieldId} is required`);
        } else if (field.type === 'text' && field.id.includes('folder') && !validateFolderPath(value)) {
            isValid = false;
            field.classList.add('is-invalid');
            errors.push(`${field.previousElementSibling?.textContent || fieldId} contains invalid characters`);
        }
    });
    
    if (!isValid) {
        showNotification(`Please fix the following errors:\n${errors.join('\n')}`, 'error');
    }
    
    return isValid;
}

// API helpers
async function apiCall(endpoint, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        }
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    try {
        const response = await fetch(endpoint, options);
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.message || `HTTP error! status: ${response.status}`);
        }
        
        return result;
    } catch (error) {
        console.error('API call error:', error);
        throw error;
    }
}

// Utility functions
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Storage helpers
function saveToLocalStorage(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
        return true;
    } catch (error) {
        console.error('Failed to save to localStorage:', error);
        return false;
    }
}

function loadFromLocalStorage(key, defaultValue = null) {
    try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : defaultValue;
    } catch (error) {
        console.error('Failed to load from localStorage:', error);
        return defaultValue;
    }
}

// Export functions for use in other scripts
window.ScheminiManager = {
    selectFolder: async function() {
        try {
            const response = await fetch('/api/select-folder-dialog', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            const result = await response.json();
            
            if (result.success) {
                return result.path;
            } else {
                console.warn('Folder selection cancelled or failed:', result.message);
                return null;
            }
        } catch (error) {
            console.error('Error selecting folder:', error);
            showNotification('Error opening folder selection dialog', 'error');
            return null;
        }
    },
    updateUserReferenceFolder: async function(folderPath) {
        if (!folderPath) return;
        try {
            const result = await apiCall('/api/user/reference-folder', 'POST', { folder_path: folderPath });
            if (result.success) {
                console.log('User reference folder updated successfully.');
                // Optionally show a subtle notification
                // showNotification('Default reference folder updated', 'success', 2000);
            } else {
                console.error('Failed to update user reference folder:', result.message);
                showNotification('Could not save reference folder: ' + result.message, 'error');
            }
        } catch (error) {
            console.error('Error updating user reference folder:', error);
            showNotification('An error occurred while saving the reference folder.', 'error');
        }
    },
    showNotification,
    setLoadingState,
    startProgressMonitoring,
    stopProgressMonitoring,
    startLogMonitoring,
    stopLogMonitoring,
    selectFolder,
    validateForm,
    apiCall,
    formatFileSize,
    formatDateTime,
    escapeHtml,
    debounce,
    throttle,
    saveToLocalStorage,
    loadFromLocalStorage
};

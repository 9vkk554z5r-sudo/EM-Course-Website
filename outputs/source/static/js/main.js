// Main JavaScript for Electron Microscopy Course
document.addEventListener('DOMContentLoaded', function() {
    // Auto-hide flash messages after 5 seconds
    var flashes = document.querySelectorAll('.flash-message');
    flashes.forEach(function(flash) {
        setTimeout(function() {
            flash.style.opacity = '0';
            flash.style.transform = 'translateY(-10px)';
            flash.style.transition = 'all 0.3s ease';
            setTimeout(function() {
                if (flash.parentNode) flash.remove();
            }, 300);
        }, 5000);
    });
});

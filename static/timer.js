let activeTimer = null; // Reference to the active timer interval
let timerEndTime = null; // Track the end time of the current timer

async function pollCommands() {
    while (true) {
        const response = await fetch('/commands');
        const data = await response.json();

        if (data && data.action === 'timer') {
            const duration = data.duration * 60; // Convert minutes to seconds
            startNewTimer(duration);
        }

        await new Promise(r => setTimeout(r, 1000));
    }
}

function startNewTimer(duration) {
    // Cancel any existing timer
    if (activeTimer) {
        clearInterval(activeTimer);
        activeTimer = null;
    }

    const overlay = document.getElementById('timer-overlay');
    const progressPath = document.querySelector('#timer-progress path');
    const timerText = document.getElementById('timer-remaining');
    
    overlay.style.display = 'block';
    const startTime = Date.now();
    timerEndTime = startTime + duration * 1000;

    // Update the timer at regular intervals
    activeTimer = setInterval(() => {
        const now = Date.now();
        const remainingTime = Math.max(0, Math.floor((timerEndTime - now) / 1000));
        const percentage = ((duration - remainingTime) / duration) * 100;

        // Update the progress pie
        progressPath.setAttribute('stroke-dasharray', `${percentage}, 100`);

        // Update the remaining time
        const minutes = Math.floor(remainingTime / 60);
        const seconds = remainingTime % 60;
        timerText.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;

        // If time is up, clear the timer
        if (remainingTime === 0) {
            clearInterval(activeTimer);
            activeTimer = null;
            overlay.style.display = 'none';
        }
    }, 1000);
}

pollCommands();

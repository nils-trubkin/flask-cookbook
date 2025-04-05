function fetchPage(path) {
    showAlert("Opening recipe page");
    fetch(path)
        .then(response => {
            if (response.ok) {
                console.log(path + " fetched");
            document.getElementById("alert-overlay").classList.remove("is-active");
            } else if (response.status === 400) {
                response.text().then(errorMessage => {
                    showAlert(errorMessage); // Pass the actual error message
                });
            }
        });
}

function openLink() {
    fetch('/open_link?url=' + document.getElementById('url').value)
        .then(response => {
            if (response.ok) {
                console.log("link opened");
            } else if (response.status === 400) {
                response.text().then(errorMessage => {
                    showAlert(errorMessage); // Pass the actual error message
                });
            }
        });
}

function reload(path) {
    fetch(path);
    showAlert("Page reloading in 5 seconds");
    // Update time to reload every second, make sure plural is used correctly do not show 0 seconds
    let seconds = 5;
    const interval = setInterval(() => {
        seconds--;
        if (seconds === 1) {
            document.getElementById("alert-message").textContent = "Page reloading in 1 second";
        } else if (seconds === 0) {
            clearInterval(interval);
        } else {
            document.getElementById("alert-message").textContent = "Page reloading in " + seconds + " seconds";
        }
    }, 1000);
    setTimeout(() => {
        window.location.reload();
    }, 5000);
}

function handleEnterKey(event) {
    if (event.key === 'Enter') {
        event.preventDefault();  // Prevent form submission
        searchRecipes(event);    // Call your custom search function
    }
}

function searchRecipes(event) {
    event.preventDefault();  // Prevent form submission on other cases
    searchRecipes();
}

function searchRecipes() {
    // Remove all tag selections
    const tags = document.getElementsByClassName('tag');
    for (let i = 0; i < tags.length; i++) {
        tags[i].classList.remove('is-selected');
        tags[i].classList.remove('is-info');
        tags[i].classList.add('is-primary');
    }

    // Get the form element
    const form = document.getElementById('searchForm');

    // Perform a POST request with the form data
    fetch('/find', {
        method: 'POST',
        body: new FormData(form), // Send form data
    })
    .then(response => response.text()) // Parse the response as text (HTML or JSON)
    .then(data => {
        // You can update the DOM with the response data here
        document.getElementById('recipes').innerHTML = data;

    })
    .catch(error => {
        console.error('Error:', error);
    });
}

// flutag as args to /find
function filterRecipes(tagElement, tag) {
    if (tagElement.classList.contains('is-selected')) {
        tagElement.classList.remove('is-selected');
        searchRecipes();
        return;
    }
    const tags = document.getElementsByClassName('tag');
    for (let i = 0; i < tags.length; i++) {
        tags[i].classList.remove('is-selected');
        tags[i].classList.remove('is-info');
        tags[i].classList.add('is-primary');
    }
    tagElement.classList.add('is-selected');
    tagElement.classList.remove('is-primary'); // Remove the primary color if needed
    tagElement.classList.add('is-info'); // Change to the "selected" color
    // Remove search text
    document.getElementById('search').value = '';

    // Get the form element
    const form = document.getElementById('searchForm');

    // Perform a POST request with the form data
    fetch('/find?tag=' + tag, {
        method: 'POST',
        body: new FormData(form), // Send form data
    })
    .then(response => response.text()) // Parse the response as text (HTML or JSON)
    .then(data => {
        // You can update the DOM with the response data here
        document.getElementById('recipes').innerHTML = data;

    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function showAlert(message) {
    const alertOverlay = document.getElementById("alert-overlay");
    const alertMessage = document.getElementById("alert-message");

    alertMessage.textContent = message; // Set the alert message
    alertOverlay.classList.add("is-active"); // Show the modal
}

// listen to text input in search bar and call searchRecipes function after 500ms
// to avoid calling the function on every key press
let timeout = null;
document.getElementById('search').addEventListener('input', () => {
    clearTimeout(timeout);
    timeout = setTimeout(searchRecipes, 500);
});

document.getElementById("alert-close").addEventListener("click", () => {
    document.getElementById("alert-overlay").classList.remove("is-active");
});

document.querySelector(".modal-close").addEventListener("click", () => {
    document.getElementById("alert-overlay").classList.remove("is-active");
});

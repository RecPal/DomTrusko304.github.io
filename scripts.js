function toggleDropdown(event, id) {
    let dropdown = document.getElementById(id);

    

    // Close the dropdown if clicking the same button again
    if (dropdown.style.display === "block" && dropdown.dataset.activeButton === event.innerText) {
        dropdown.style.display = "none";
        return;
    }

    // Close all other dropdowns first
    document.querySelectorAll(".dropdown-content").forEach(d => {
        if (d !== dropdown) {
            d.style.display = "none";
        }
    });

    // Ensure only one dropdown is open
    dropdown.style.display = "block";
    dropdown.dataset.activeButton = event.innerText;

    // Get button position relative to viewport
    let rect = event.getBoundingClientRect();

    // Position dropdown globally (relative to body)
    dropdown.style.left = `${rect.left}px`;
    dropdown.style.top = `${rect.bottom + window.scrollY}px`;
}

// Close dropdown when clicking outside
document.addEventListener("click", function (event) {
    if (!event.target.matches(".horizontal-content-selection")) {
        document.getElementById("global-dropdown").style.display = "none";
    }
});


document.querySelectorAll(".zoomable-image").forEach(image => {
    image.addEventListener("click", function () {
        this.classList.toggle("zoomed");

        // Enable scrolling if zoomed in
        let container = this.closest(".zoomable-container");
        if (this.classList.contains("zoomed")) {
            container.style.overflow = "scroll"; // Allow scrolling
        } else {
            container.style.overflow = "hidden"; // Reset scrolling when zoomed out
        }
    });
});


fetch("https://recpal.github.io/DomTrusko304.github.io/Taskbar.html")
    .then(response => response.text())
    .then(data => {
        document.getElementById("header").innerHTML = data;
    });
// SheCareer JavaScript

let currentLanguage = "en";
let selectedCategory = "All";

const jobs = [
    {name:"Banking Recruitment",category:"Banking",location:"Central"},
    {name:"Police Recruitment",category:"Police",location:"Maharashtra"},
    {name:"Railway Recruitment",category:"Railway",location:"Central"},
    {name:"Teaching Recruitment",category:"Teaching",location:"Maharashtra"},
    {name:"Medical Recruitment",category:"Medical",location:"Central"},
    {name:"UPSC Recruitment",category:"UPSC",location:"Central"},
    {name:"MPSC Recruitment",category:"MPSC",location:"Maharashtra"},
    {name:"Defence Recruitment",category:"Defence",location:"Central"},
    {name:"SSC Recruitment",category:"SSC",location:"Central"},
    {name:"Other Government Recruitment",category:"Other",location:"Maharashtra"}
];

const translations = {
    en: {
        location: "Location",
        central: "Central Government",
        maharashtra: "Maharashtra",
        category: "Category",
        details: "View Details",
        check: "Please check the official government notification for eligibility, salary, application dates and other details.",
        noResults: "No jobs found. Please try another search.",
        demo: "Demo category - No live vacancy is being advertised here."
    },
    mr: {
        location: "ठिकाण",
        central: "केंद्र सरकार",
        maharashtra: "महाराष्ट्र",
        category: "विभाग",
        details: "माहिती पहा",
        check: "पात्रता, पगार, अर्जाच्या तारखा आणि इतर माहितीसाठी संबंधित सरकारी अधिकृत जाहिरात तपासा.",
        noResults: "नोकरी सापडली नाही. दुसरा शब्द शोधून पहा.",
        demo: "हा नमुना विभाग आहे. येथे सध्या प्रत्यक्ष भरतीची जाहिरात दिलेली नाही."
    }
};

// JOB CARDS

function displayJobs() {

    const container = document.getElementById("jobContainer");
    const search = document.getElementById("searchInput").value.toLowerCase();
    const location = document.getElementById("locationFilter").value;

    container.innerHTML = "";

    const filteredJobs = jobs.filter(job => {

        const matchesSearch =
            job.name.toLowerCase().includes(search) ||
            job.category.toLowerCase().includes(search);

        const matchesCategory =
            selectedCategory === "All" ||
            job.category === selectedCategory;

        const matchesLocation =
            location === "" || job.location === location;

        return matchesSearch && matchesCategory && matchesLocation;
    });

    filteredJobs.forEach(job => {

        const card = document.createElement("div");
        card.className = "job-card";

        const title = document.createElement("h3");
        title.textContent = job.name;

        const category = document.createElement("p");
        category.textContent =
            translations[currentLanguage].category + ": " + job.category;

        const place = document.createElement("p");
        place.textContent =
            translations[currentLanguage].location + ": " +
            (job.location === "Central"
                ? translations[currentLanguage].central
                : translations[currentLanguage].maharashtra);

        const button = document.createElement("button");
        button.textContent = translations[currentLanguage].details;

        button.addEventListener("click", function() {
            showJobDetails(job);
        });

        card.appendChild(title);
        card.appendChild(category);
        card.appendChild(place);
        card.appendChild(button);

        container.appendChild(card);
    });

    const noResults = document.getElementById("noResults");

    noResults.hidden = filteredJobs.length !== 0;

    if (filteredJobs.length === 0) {
        noResults.textContent = translations[currentLanguage].noResults;
    }
}

// SEARCH BUTTON

document.getElementById("searchBtn").addEventListener("click", function() {
    displayJobs();
});

// ENTER KEY SEARCH

document.getElementById("searchInput").addEventListener("keydown", function(event) {
    if (event.key === "Enter") {
        displayJobs();
    }
});

// LOCATION FILTER

document.getElementById("locationFilter").addEventListener("change", function() {
    displayJobs();
});

// CATEGORY FILTER

document.querySelectorAll(".category-card").forEach(button => {

    button.addEventListener("click", function() {

        selectedCategory = this.dataset.category;

        displayJobs();

        document.getElementById("jobs").scrollIntoView({
            behavior: "smooth"
        });

    });

});

// RESET FILTERS

document.getElementById("resetBtn").addEventListener("click", function() {

    selectedCategory = "All";

    document.getElementById("searchInput").value = "";
    document.getElementById("locationFilter").value = "";

    displayJobs();

});

// SHOW JOB DETAILS

function showJobDetails(job) {

    const modal = document.getElementById("jobModal");

    document.getElementById("modalTitle").textContent = job.name;

    document.getElementById("modalBody").innerHTML = `
        <p><strong>${translations[currentLanguage].category}:</strong> ${job.category}</p>

        <p><strong>${translations[currentLanguage].location}:</strong>
        ${job.location === "Central"
            ? translations[currentLanguage].central
            : translations[currentLanguage].maharashtra}</p>

        <p>${translations[currentLanguage].demo}</p>

        <p>${translations[currentLanguage].check}</p>
    `;

    modal.style.display = "flex";
}

// CLOSE POPUP

function closeModal() {
    document.getElementById("jobModal").style.display = "none";
}

document.getElementById("closeModal").addEventListener("click", closeModal);

document.getElementById("modalCloseBtn").addEventListener("click", closeModal);

document.getElementById("jobModal").addEventListener("click", function(event) {
    if (event.target === this) {
        closeModal();
    }
});

document.addEventListener("keydown", function(event) {
    if (event.key === "Escape") {
        closeModal();
    }
});

// LANGUAGE SWITCH

document.getElementById("languageBtn").addEventListener("click", function() {

    currentLanguage = currentLanguage === "en" ? "mr" : "en";

    document.querySelectorAll("[data-en][data-mr]").forEach(element => {

        element.textContent = element.getAttribute("data-" + currentLanguage);

    });

    const searchInput = document.getElementById("searchInput");

    searchInput.placeholder =
        searchInput.getAttribute("data-" + currentLanguage + "-placeholder");

    this.textContent = currentLanguage === "en" ? "मराठी" : "English";

    displayJobs();

});

// INITIAL LOAD

displayJobs();
alert("SheCareer JavaScript Connected!");
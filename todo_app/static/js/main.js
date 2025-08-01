let tasks = JSON.parse(localStorage.getItem("tasks") || "[]");
const taskList = document.getElementById("taskList");
const taskInput = document.getElementById("taskInput");
const reminderInput = document.getElementById("reminderInput");
const repeatInput = document.getElementById("repeatInput");
const tagInput = document.getElementById("tagInput");
const reminderToggle = document.getElementById("reminderToggle");
const emailField = document.getElementById("emailField");
const progressStats = document.getElementById("progressStats");

// Modal elements
const oldTasksModal = document.getElementById("oldTasksModal");
const oldTasksModalContent = document.getElementById("oldTasksModalContent");
const closeModalBtn = document.getElementById("closeModalBtn");
const calendarInput = document.getElementById("calendarInput");


// Initialize Flatpickr for the calendar input
flatpickr(calendarInput, {
    dateFormat: "Y-m-d",
    maxDate: "today", // Don't allow selecting future dates
    onChange: function(selectedDates, dateStr, instance) {
        if (selectedDates.length > 0) {
            viewOldTasks(dateStr); // Pass the selected date string
        }
    }
});


function renderTasks() {
    taskList.innerHTML = "";
    // Filter out tasks that are done and not repeating, if they were completed yesterday or earlier.
    // This simulates the "day end" removal visually.
    const now = new Date();
    now.setHours(0,0,0,0); // Start of today

    const activeTasks = tasks.filter(task => {
        if (!task.done) return true; // Keep all undone tasks
        if (task.repeat) return true; // Keep repeating tasks even if done

        // For one-time tasks, if done, remove from main list display if completed before today
        if (task.completedAt) {
            const completedDate = new Date(task.completedAt);
            completedDate.setHours(0,0,0,0);
            return completedDate.getTime() === now.getTime(); // Only show if completed today
        }
        return true; // Should not happen, but a fallback
    });


    activeTasks.forEach((task, i) => {
        const remindTime = task.remindAt ? new Date(task.remindAt).toLocaleString() : "No reminder set";
        const tags = task.tags && task.tags.length > 0 ? `Tags: ${task.tags.join(", ")}` : "";
        const completedTime = task.completedAt ? `Completed: ${new Date(task.completedAt).toLocaleString()}` : "";

        const li = document.createElement("li");
        li.className = "flex justify-between items-center bg-gray-100 dark:bg-gray-800 px-4 py-2 rounded";
        li.innerHTML = `
            <div>
                <span class="${task.done ? "line-through text-gray-500" : ""} font-semibold">${task.text}</span><br />
                <small class="text-gray-600 dark:text-gray-400">Reminder: ${remindTime}</small>
                ${task.repeat ? `<br/><small class="text-sm italic text-indigo-400">Repeats: ${task.repeat}</small>` : ""}
                ${tags ? `<br/><small class="text-sm italic text-pink-400">${tags}</small>` : ""}
                ${task.done && task.completedAt ? `<br/><small class="text-xs text-green-500">${completedTime}</small>` : ""}
            </div>
            <div class="space-x-2">
                <button onclick="toggleDone(${i})" class="text-green-600 hover:underline">${task.done ? "Undo" : "Done"}</button>
                <button onclick="deleteTask(${i})" class="text-red-600 hover:underline">Delete</button>
            </div>
        `;
        taskList.appendChild(li);
    });
    displayProgressStats(); // Update stats after rendering tasks
}

function addTask() {
    const text = taskInput.value.trim();
    if (text === "") return;

    const remindAtValue = reminderInput.value;
    const repeat = repeatInput.value;
    const tagsValue = tagInput.value.trim();
    const tags = tagsValue ? tagsValue.split(",").map(t => t.trim()).filter(t => t) : [];

    let remindAt = null;
    if (remindAtValue) {
        const date = new Date(remindAtValue);
        if (!isNaN(date.getTime())) {
            remindAt = date.toISOString();
        } else {
            alert("Invalid reminder time!");
            return;
        }
    }

    tasks.push({
        text,
        done: false,
        remindAt,
        emailed: false,
        repeat,
        tags,
        completedAt: null
    });

    saveTasks();
    taskInput.value = "";
    reminderInput.value = "";
    repeatInput.value = "";
    tagInput.value = "";
    renderTasks();
}

function deleteTask(i) {
    tasks.splice(i, 1);
    saveTasks();
    renderTasks();
}

function toggleDone(i) {
    tasks[i].done = !tasks[i].done;
    tasks[i].completedAt = tasks[i].done ? new Date().toISOString() : null;
    saveTasks();
    renderTasks(); // Update stats after toggling
}

function saveTasks() {
    localStorage.setItem("tasks", JSON.stringify(tasks));
    syncTasksToBackend();
}

function syncTasksToBackend() {
    const userId = getOrCreateUserId();
    fetch("/save-tasks/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCSRFToken(),
        },
        body: JSON.stringify({
            user_id: userId,
            tasks: tasks
        }),
    });
}

function toggleEmailField() {
    emailField.classList.toggle("hidden", !reminderToggle.checked);
}

function saveEmail() {
    const email = document.getElementById("emailInput").value.trim();
    if (!email.includes("@")) return alert("Enter a valid email!");

    const userId = getOrCreateUserId();

    fetch("/save-email/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCSRFToken()
        },
        body: JSON.stringify({
            user_id: userId,
            email: email
        }),
    }).then((res) => (res.ok ? alert("Email saved!") : alert("Error saving email")));
}

function getOrCreateUserId() {
    let id = localStorage.getItem("user_id");
    if (!id) {
        id = crypto.randomUUID();
        localStorage.setItem("user_id", id);
    }
    return id;
}

function getCSRFToken() {
    const cookie = document.cookie.split(";").find((c) => c.trim().startsWith("csrftoken="));
    return cookie ? cookie.split("=")[1] : "";
}

function getStartOfWeek(date) {
    const d = new Date(date);
    const day = d.getDay(); // 0 for Sunday, 6 for Saturday
    const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Adjust to Monday
    d.setDate(diff);
    d.setHours(0, 0, 0, 0);
    return d;
}

function displayProgressStats() {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    let completedToday = 0;
    let totalTasksToday = 0; // This should ideally count tasks that were *due* or active today

    const weeklyCompletion = new Array(7).fill(0); // 0: Mon, 1: Tue, ..., 6: Sun
    const startOfWeek = getStartOfWeek(new Date());

    tasks.forEach(task => {
        // Only count tasks that were 'active' today or completed today for 'Today's Progress'
        const isTodayTask = (task.remindAt && new Date(task.remindAt).toDateString() === today.toDateString()) ||
                            (task.completedAt && new Date(task.completedAt).toDateString() === today.toDateString()) ||
                            (task.repeat && !task.done); // Assume repeating tasks are always "today's" until done

        if (isTodayTask) {
             totalTasksToday++; // Count active/relevant tasks for today's total
             if (task.done && task.completedAt && new Date(task.completedAt).toDateString() === today.toDateString()) {
                completedToday++;
            }
        }


        // Stats for the week
        if (task.completedAt) {
            const completedDate = new Date(task.completedAt);
            if (completedDate >= startOfWeek) {
                const dayIndex = (completedDate.getDay() + 6) % 7; // Convert to 0 for Monday, 6 for Sunday
                weeklyCompletion[dayIndex]++;
            }
        }
    });

    const totalTasks = tasks.length; // This counts all tasks ever added
    const totalDoneTasks = tasks.filter(t => t.done).length;

    const percentageToday = totalTasksToday > 0 ? ((completedToday / totalTasksToday) * 100).toFixed(0) : 0;
    const percentageOverall = totalTasks > 0 ? ((totalDoneTasks / totalTasks) * 100).toFixed(0) : 0;

    let weeklyChartHtml = `
        <h3 class="text-xl font-semibold mb-2">Weekly Completion</h3>
        <div class="flex justify-around items-end h-20 bg-gray-200 dark:bg-gray-700 rounded p-1 mb-4">
    `;

    const maxCompleted = Math.max(...weeklyCompletion, 1); // Ensure division by zero is avoided
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

    weeklyCompletion.forEach((count, index) => {
        const height = (count / maxCompleted) * 100; // Height as percentage
        weeklyChartHtml += `
            <div class="flex flex-col items-center justify-end h-full">
                <span class="text-xs mb-1">${count}</span>
                <div class="w-4 bg-blue-500 rounded-t" style="height: ${height}%;"></div>
                <span class="text-xs mt-1">${days[index]}</span>
            </div>
        `;
    });
    weeklyChartHtml += `</div>`;


    progressStats.innerHTML = `
        <h2 class="text-2xl font-bold mb-3 text-center">Progress Stats</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg shadow">
                <h3 class="text-xl font-semibold mb-2">Today's Progress</h3>
                <p class="text-lg">${completedToday} of ${totalTasksToday} tasks completed today (${percentageToday}%)</p>
            </div>
            <div class="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg shadow">
                <h3 class="text-xl font-semibold mb-2">Overall Progress</h3>
                <p class="text-lg">${totalDoneTasks} of ${totalTasks} tasks completed overall (${percentageOverall}%)</p>
            </div>
        </div>
        <div class="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg shadow mt-4">
            ${weeklyChartHtml}
        </div>
    `;
}

// --- Modal Functions for Old Tasks ---
function openModal() {
    oldTasksModal.classList.remove("hidden");
    oldTasksModal.classList.add("flex"); // Use flex for centering
}

function closeModal() {
    oldTasksModal.classList.add("hidden");
    oldTasksModal.classList.remove("flex");
}

async function viewOldTasks(dateStr) {
    const userId = getOrCreateUserId();
    if (!dateStr) return; // Don't proceed if no date selected

    try {
        const response = await fetch(`/get-tasks-by-date/?user_id=${userId}&date=${dateStr}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        renderModalTasks(dateStr, data.tasks);
        openModal();
    } catch (error) {
        console.error("Error fetching old tasks:", error);
        alert("Failed to load tasks for the selected date.");
    }
}

function renderModalTasks(date, tasksForDate) {
    oldTasksModalContent.innerHTML = `
        <h3 class="text-xl font-bold mb-4">Tasks for ${date}</h3>
        <div class="space-y-2">
    `;

    if (tasksForDate.length === 0) {
        oldTasksModalContent.innerHTML += `<p class="text-gray-500">No tasks found for this date.</p>`;
    } else {
        const doneTasks = tasksForDate.filter(t => t.done);
        const undoneTasks = tasksForDate.filter(t => !t.done);

        if (undoneTasks.length > 0) {
            oldTasksModalContent.innerHTML += `<h4 class="font-semibold mt-4">Pending Tasks:</h4>`;
            undoneTasks.forEach(task => {
                oldTasksModalContent.innerHTML += `<p class="pl-4">- ${task.text} ${task.remindAt ? `(Reminder: ${new Date(task.remindAt).toLocaleString()})` : ''}</p>`;
            });
        }

        if (doneTasks.length > 0) {
            oldTasksModalContent.innerHTML += `<h4 class="font-semibold mt-4">Completed Tasks:</h4>`;
            doneTasks.forEach(task => {
                oldTasksModalContent.innerHTML += `<p class="pl-4 line-through text-gray-500">- ${task.text} ${task.completedAt ? `(Completed: ${new Date(task.completedAt).toLocaleString()})` : ''}</p>`;
            });
        }
    }
    oldTasksModalContent.innerHTML += `</div>`;
}

// Event Listeners for modal
closeModalBtn.addEventListener("click", closeModal);
// Close modal when clicking outside of it
window.addEventListener("click", (event) => {
    if (event.target === oldTasksModal) {
        closeModal();
    }
});


renderTasks();
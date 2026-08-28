const form = document.querySelector("#chat-form");
const input = document.querySelector("#question");
const submit = document.querySelector("#submit");
const messages = document.querySelector("#messages");

function addMessage(text, role) {
  const node = document.createElement("article");
  node.className = `message ${role}`;
  node.textContent = text;
  messages.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
  return node;
}

async function sendFeedback(question, answer, relevant, container) {
  container.textContent = "Terima kasih atas masukannya.";
  try {
    await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, answer, relevant }),
    });
  } catch (error) {
    // Feedback is best-effort; a failed submission shouldn't disrupt the chat.
  }
}

function addFeedbackControls(question, answer) {
  const container = document.createElement("div");
  container.className = "feedback";
  const label = document.createElement("span");
  label.textContent = "Jawaban ini relevan?";
  const yes = document.createElement("button");
  yes.type = "button";
  yes.textContent = "👍 Ya";
  const no = document.createElement("button");
  no.type = "button";
  no.textContent = "👎 Tidak";
  yes.addEventListener("click", () => sendFeedback(question, answer, true, container));
  no.addEventListener("click", () => sendFeedback(question, answer, false, container));
  container.append(label, yes, no);
  messages.appendChild(container);
  messages.scrollTop = messages.scrollHeight;
}

async function ask(question) {
  document.querySelector(".welcome")?.remove();
  addMessage(question, "user");
  submit.disabled = true;
  submit.firstChild.textContent = "Menelusuri ";
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Layanan tidak dapat menjawab.");
    addMessage(payload.answer, "assistant");
    const route = document.createElement("p");
    route.className = "route";
    route.textContent = `Rute pencarian: ${payload.plan.route} · ${payload.plan.queries.length} query`;
    messages.appendChild(route);
    addFeedbackControls(question, payload.answer);
  } catch (error) {
    addMessage(`Maaf, terjadi kendala: ${error.message}`, "assistant");
  } finally {
    submit.disabled = false;
    submit.firstChild.textContent = "Telusuri ";
    input.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (question.length < 3) return;
  input.value = "";
  ask(question);
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

document.querySelectorAll(".suggestions button").forEach((button) => {
  button.addEventListener("click", () => { input.value = button.textContent; form.requestSubmit(); });
});

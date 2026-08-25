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

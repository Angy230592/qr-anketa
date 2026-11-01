const timer = document.getElementById("timer");
const started = Date.now();

function tick() {
  if (!timer) return;
  const sec = Math.floor((Date.now() - started) / 1000);
  const m = Math.floor(sec / 60);
  const s = String(sec % 60).padStart(2, "0");
  timer.textContent = `${m}:${s}`;
}
setInterval(tick, 1000);

document.querySelectorAll('input[data-single="1"]').forEach((box) => {
  box.addEventListener("change", () => {
    if (!box.checked) return;
    const name = box.name;
    document.querySelectorAll(`input[name="${name}"]`).forEach((other) => {
      if (other !== box) other.checked = false;
    });
  });
});

const canvas = document.createElement("canvas");
canvas.style.position = "fixed";
canvas.style.top = "0";
canvas.style.left = "0";
document.body.appendChild(canvas);

// Get the 2D drawing context
const ctx = canvas.getContext("2d");

// Update canvas dimensions on window resize
function updateCanvasDimensions() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
}
updateCanvasDimensions(); // Initialize canvas dimensions
window.addEventListener("resize", updateCanvasDimensions);

// Event listener for mousemove
document.addEventListener("mousemove", event => {
  const x = event.clientX;
  const y = event.clientY + window.scrollY; // Account for scroll position

  // Draw a smaller red dot at the mouse coordinates
  ctx.fillStyle = "red";
  ctx.beginPath();
  ctx.arc(x, y, 3, 0, Math.PI * 2);
  ctx.fill();
});

// Create a button to clear the points
const clearButton = document.createElement("button");
clearButton.textContent = "Clear Points";
clearButton.style.position = "fixed";
clearButton.style.top = "10px";
clearButton.style.left = "10px";
clearButton.id = "clear"
clearButton.addEventListener("click", () => {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
});
document.body.appendChild(clearButton);

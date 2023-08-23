const canvas = document.createElement("canvas");
canvas.style.position = "fixed";
canvas.style.top = "0";
canvas.style.left = "0";
canvas.style.zIndex = "999"; // Set higher z-index for canvas
canvas.width = window.innerWidth; // Set canvas dimensions to cover the full document
canvas.height = window.innerHeight;
document.body.appendChild(canvas);

// Get the 2D drawing context
const ctx = canvas.getContext("2d");

// Event listener for mousemove
let lastEventTime = 0;
let timeSinceClear = 0; // Track time since last clear
const timeDeltaData = [];

document.addEventListener("mousemove", event => {
  const currentTime = Date.now();
  const delta = currentTime - lastEventTime;

  if (delta <= 100) { // Ignore time-deltas larger than 0.1 seconds
    if (lastEventTime !== 0) {
      timeSinceClear += delta;

      // Add the new time-delta to the data array
      timeDeltaData.push(delta);

      const averageDelta = timeDeltaData.length === 0 ? 0 : timeDeltaData.reduce((sum, value) => sum + value) / timeDeltaData.length;
      const frequency = averageDelta === 0 ? 0 : 1000 / averageDelta; // Calculate frequency in Hz

      tab.textContent = `Average Frequency: ${frequency.toFixed(2)} Hz, count:${timeDeltaData.length}`;

      // Draw the time-delta graph
      drawTimeDeltaGraph();
    } else {
      tab.textContent = "Average Frequency: 0.00 Hz, count:0"; // Set initial content
    }
  }

  lastEventTime = currentTime;

  const x = event.clientX;
  const y = event.clientY + window.scrollY; // Account for scroll position

  // Draw a smaller red dot at the mouse coordinates
  ctx.fillStyle = "red";
  ctx.beginPath();
  ctx.arc(x, y, 3, 0, Math.PI * 2);
  ctx.fill();
});

// Create a button to clear the points and reset time-delta
const clearButton = document.createElement("button");
clearButton.textContent = "Clear";
clearButton.style.position = "fixed";
clearButton.style.top = "10px";
clearButton.style.left = "10px";
clearButton.id = "clear"; // Add the "clear" ID to the button
clearButton.style.zIndex = "1000"; // Set lower z-index for the button
clearButton.addEventListener("click", () => {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  lastEventTime = 0;
  timeSinceClear = 0;
  timeDeltaData.length = 0; // Clear the time-delta data
  tab.textContent = "Average Frequency: 0.00 Hz, count:0";
  drawTimeDeltaGraph();
});
document.body.appendChild(clearButton);

// Create the tab-like element for displaying average frequency
const tab = document.createElement("div");
tab.style.position = "fixed";
tab.style.top = "10px"; // Adjust the position to avoid overdrawn elements
tab.style.right = "10px";
tab.style.backgroundColor = "lightgray";
tab.style.padding = "5px 10px";
tab.style.borderRadius = "5px";
tab.style.cursor = "pointer";
tab.style.fontFamily = "Arial, sans-serif";
tab.style.fontSize = "14px";
tab.style.fontWeight = "bold";
tab.textContent = "Average Frequency: 0.00 Hz, count:0";
document.body.appendChild(tab);

// Create the graph canvas
const graphCanvas = document.createElement("canvas");
graphCanvas.width = window.innerWidth;
graphCanvas.height = 200; // Set an initial height
graphCanvas.style.position = "fixed";
graphCanvas.style.bottom = "0";
graphCanvas.style.left = "0";
graphCanvas.style.zIndex = "998"; // Set lower z-index than other elements
document.body.appendChild(graphCanvas);

// Function to draw the time-delta graph
function drawTimeDeltaGraph() {
  const graphCtx = graphCanvas.getContext("2d");

  // Clear the graph canvas
  graphCtx.clearRect(0, 0, graphCanvas.width, graphCanvas.height);

  // Restart the graph if it runs out of space
  if (timeDeltaData.length > graphCanvas.width) {
    timeDeltaData.splice(0, timeDeltaData.length - graphCanvas.width);
  }

  const maxTimeDelta = Math.max(...timeDeltaData);
  const scaleFactor = graphCanvas.height / maxTimeDelta;

  // Draw the grid
  const gridSpacing = 20; // Adjust this value as needed
  graphCtx.strokeStyle = "lightgray";
  graphCtx.beginPath();
  for (let y = 0; y <= graphCanvas.height; y += gridSpacing) {
    graphCtx.moveTo(0, y);
    graphCtx.lineTo(graphCanvas.width, y);
    const timeValue = (maxTimeDelta * (graphCanvas.height - y) / graphCanvas.height).toFixed(2);
    if (isFinite(timeValue)) {
      graphCtx.fillText(timeValue + " ms", graphCanvas.width - 50, y + 12);
    }
  }
  graphCtx.stroke();

  // Draw the graph lines
  graphCtx.beginPath();
  graphCtx.strokeStyle = "gray";
  graphCtx.moveTo(0, 0);
  graphCtx.lineTo(graphCanvas.width, 0);
  graphCtx.stroke();

  graphCtx.beginPath();
  graphCtx.strokeStyle = "gray";
  graphCtx.moveTo(0, graphCanvas.height);
  graphCtx.lineTo(graphCanvas.width, graphCanvas.height);
  graphCtx.stroke();

  // Draw the time-delta data
  graphCtx.beginPath();
  graphCtx.strokeStyle = "blue";
  graphCtx.moveTo(0, graphCanvas.height - timeDeltaData[0] * scaleFactor);

  for (let i = 1; i < timeDeltaData.length; i++) {
    graphCtx.lineTo(i, graphCanvas.height - timeDeltaData[i] * scaleFactor);
  }

  graphCtx.stroke();

  // Draw x and y labels
  graphCtx.fillStyle = "black";
  graphCtx.font = "12px Arial";
  graphCtx.fillText("0 ms", 2, graphCanvas.height - 2);
  graphCtx.fillText(`${timeDeltaData.length - 1} ms`, graphCanvas.width - 30, graphCanvas.height - 2);
  graphCtx.fillText(`${maxTimeDelta.toFixed(2)} ms`, 2, 10);
}

// Update canvas dimensions on window resize
function updateCanvasDimensions() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  graphCanvas.width = window.innerWidth; // Update graph canvas width
  drawTimeDeltaGraph();
}
window.addEventListener("resize", updateCanvasDimensions);
updateCanvasDimensions(); // Initialize canvas dimensions

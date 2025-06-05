/**
 * Creates a debug mask in the exact format expected by Azure OpenAI's image editing API
 * and outputs it to a new tab for inspection
 */
export function createAndShowDebugMask(
  maskCanvas: HTMLCanvasElement,
  originalWidth: number,
  originalHeight: number
): void {
  // Check aspect ratios
  const drawingAspectRatio = maskCanvas.width / maskCanvas.height;
  const targetAspectRatio = originalWidth / originalHeight;
  
  // Create a debug mask with proper dimensions
  const debugMaskUrl = createDebugMask(maskCanvas, originalWidth, originalHeight);
  if (!debugMaskUrl) return;
  
  // Open in new tab
  const win = window.open();
  if (!win) {
    return;
  }
  
  // Calculate scale factors
  const scaleX = originalWidth / maskCanvas.width;
  const scaleY = originalHeight / maskCanvas.height;
  
  // Check for content in the original mask
  const maskCtx = maskCanvas.getContext('2d');
  let pixelsWithDrawing = 0;
  const totalPixels = maskCanvas.width * maskCanvas.height;
  
  if (maskCtx) {
    const maskData = maskCtx.getImageData(0, 0, maskCanvas.width, maskCanvas.height);
    for (let i = 0; i < maskData.data.length; i += 4) {
      if (maskData.data[i + 3] > 0) {
        pixelsWithDrawing++;
      }
    }
  }
  
  // Write HTML content with debug info
  win.document.write(`
    <html>
      <head>
        <title>API Mask Debug</title>
        <style>
          body {
            margin: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            background: #333;
            color: white;
            font-family: system-ui, sans-serif;
          }
          h3 {
            margin-top: 10px;
          }
          .container {
            display: flex;
            gap: 20px;
            align-items: flex-start;
            flex-wrap: wrap;
            justify-content: center;
            margin: 20px;
          }
          .image-container {
            display: flex;
            flex-direction: column;
            align-items: center;
          }
          .checkerboard {
            background-image: linear-gradient(45deg, #666 25%, transparent 25%),
              linear-gradient(-45deg, #666 25%, transparent 25%),
              linear-gradient(45deg, transparent 75%, #666 75%),
              linear-gradient(-45deg, transparent 75%, #666 75%);
            background-size: 20px 20px;
            background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
            background-color: #999;
          }
          img {
            max-width: 100%;
            max-height: 80vh;
            border: 1px solid #666;
          }
          p {
            margin: 5px 0;
            max-width: 500px;
            text-align: center;
          }
          .info {
            background: #444;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
            font-family: monospace;
            width: 100%;
            max-width: 800px;
          }
          .warning {
            color: #ffcc00;
            font-weight: bold;
          }
          button {
            margin: 10px;
            padding: 8px 16px;
            background: #0066cc;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
          }
          button:hover {
            background: #0055aa;
          }
        </style>
      </head>
      <body>
        <h3>API Mask Debug View</h3>
        <div class="info">
          <div>Original drawing dimensions: ${maskCanvas.width}x${maskCanvas.height}</div>
          <div>Final mask dimensions: ${originalWidth}x${originalHeight}</div>
          <div>Scale factor: ${scaleX.toFixed(2)}x${scaleY.toFixed(2)}</div>
          <div>Drawing content: ${pixelsWithDrawing} pixels (${((pixelsWithDrawing / totalPixels) * 100).toFixed(2)}% of drawing)</div>
          ${Math.abs(drawingAspectRatio - targetAspectRatio) > 0.01 ? 
            `<div class="warning">WARNING: Aspect ratio mismatch! Drawing (${drawingAspectRatio.toFixed(2)}) vs Image (${targetAspectRatio.toFixed(2)})</div>` : 
            ''}
        </div>
        <div class="container">
          <div class="image-container">
            <p>Original Drawing (white = drawn areas)</p>
            <img src="${maskCanvas.toDataURL()}" />
          </div>
          <div class="image-container">
            <p>Actual API Mask (transparent = areas to edit)</p>
            <div class="checkerboard">
              <img src="${debugMaskUrl}" />
            </div>
          </div>
        </div>
        <p>
          The API requires a mask where transparent pixels (alpha=0) indicate areas to be edited,
          and opaque black pixels indicate areas to preserve.
        </p>
        <p>
          <strong>The mask must have exactly the same dimensions as the original image: ${originalWidth}x${originalHeight}px</strong>
        </p>
        <button onclick="window.close()">Close</button>
        <button onclick="const link = document.createElement('a'); link.download='api_mask.png'; link.href='${debugMaskUrl}'; link.click();">
          Download API Mask
        </button>
      </body>
    </html>
  `);
}

/**
 * Creates a debug mask in the exact format expected by Azure OpenAI's image editing API
 * @returns URL for the debug mask image
 */
export function createDebugMask(
  maskCanvas: HTMLCanvasElement,
  originalWidth: number,
  originalHeight: number
): string | undefined {
  console.log("Creating debug mask...");
  
  // Validate input dimensions
  if (maskCanvas.width <= 0 || maskCanvas.height <= 0) {
    console.error("Invalid mask canvas dimensions:", maskCanvas.width, "x", maskCanvas.height);
    return undefined;
  }
  
  if (originalWidth <= 0 || originalHeight <= 0) {
    console.error("Invalid original image dimensions:", originalWidth, "x", originalHeight);
    return undefined;
  }
  
  // Create a canvas for the debug mask with correct dimensions
  const debugMaskCanvas = document.createElement('canvas');
  debugMaskCanvas.width = originalWidth;
  debugMaskCanvas.height = originalHeight;
  
  const ctx = debugMaskCanvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) return undefined;
  
  // Fill the debug mask with opaque black (areas to preserve)
  ctx.fillStyle = '#000000';
  ctx.fillRect(0, 0, debugMaskCanvas.width, debugMaskCanvas.height);
  
  // Get the mask drawing and scale it properly
  const maskCtx = maskCanvas.getContext('2d', { willReadFrequently: true });
  if (!maskCtx) return undefined;
  
  try {
    // Get original mask data
    const originalMaskData = maskCtx.getImageData(0, 0, maskCanvas.width, maskCanvas.height);
    
    // Create a new ImageData for the scaled mask
    const scaledMaskData = ctx.createImageData(originalWidth, originalHeight);
    
    // Calculate scale factors
    const scaleX = originalWidth / maskCanvas.width;
    const scaleY = originalHeight / maskCanvas.height;
    
    console.log("Scale factors:", scaleX.toFixed(2), "x", scaleY.toFixed(2));
    
    // Initialize all pixels as opaque black (areas to preserve)
    for (let i = 0; i < scaledMaskData.data.length; i += 4) {
      scaledMaskData.data[i] = 0;       // R = 0
      scaledMaskData.data[i + 1] = 0;   // G = 0
      scaledMaskData.data[i + 2] = 0;   // B = 0
      scaledMaskData.data[i + 3] = 255; // Alpha = 255 (fully opaque)
    }
    
    // For each pixel in the target image
    let transparentPixels = 0;
    const totalPixels = originalWidth * originalHeight;
    
    // For each pixel in the target image
    for (let y = 0; y < originalHeight; y++) {
      for (let x = 0; x < originalWidth; x++) {
        // Find the corresponding pixel in the source mask
        const sourceX = Math.floor(x / scaleX);
        const sourceY = Math.floor(y / scaleY);
        
        // Make sure we're within bounds of the source
        if (sourceX >= 0 && sourceX < maskCanvas.width && 
            sourceY >= 0 && sourceY < maskCanvas.height) {
          
          // Get index in source data
          const sourceIndex = (sourceY * maskCanvas.width + sourceX) * 4;
          
          // Get index in target data
          const targetIndex = (y * originalWidth + x) * 4;
          
          // If source pixel has alpha > 0 (was drawn on), make target pixel transparent
          if (originalMaskData.data[sourceIndex + 3] > 0) {
            // Make pixel transparent (area to edit)
            scaledMaskData.data[targetIndex + 3] = 0; // Alpha = 0 (transparent)
            transparentPixels++;
          }
        }
      }
    }
    
    console.log(`Transparent pixels in final mask: ${transparentPixels} (${((transparentPixels / totalPixels) * 100).toFixed(2)}% of image)`);
    
    // Put the modified data back to the debug canvas
    ctx.putImageData(scaledMaskData, 0, 0);
    
    // Return data URL
    return debugMaskCanvas.toDataURL('image/png');
  } catch (error) {
    console.error("Error creating debug mask:", error);
    return undefined;
  }
}
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "updateContent") {
    document.body.innerHTML = `
      <div id="reader-mode">
        <h1>${document.title}</h1>
        ${request.content}
      </div>
    `;
    
    const style = document.createElement('style');
    style.textContent = `
      body {
        font-family: Arial, sans-serif;
        line-height: 1.6;
        padding: 20px;
        max-width: 800px;
        margin: 0 auto;
        background-color: #f0f0f0;
      }
      #reader-mode {
        background-color: white;
        padding: 20px;
        border-radius: 5px;
        box-shadow: 0 0 10px rgba(0,0,0,0.1);
      }
      h1 {
        color: #333;
      }
      p {
        margin-bottom: 15px;
      }
      .highlight {
        color: red;
        font-weight: bold;
      }
    `;
    document.head.appendChild(style);

  } else if (request.action === "showError") {
    document.body.innerHTML = `
      <div style="color: red; max-width: 800px; margin: 0 auto; font-family: Arial, sans-serif; line-height: 1.6; padding: 20px;">
        <h1>Error</h1>
        <p>${request.error}</p>
      </div>
    `;
  }
  sendResponse({received: true});  // Acknowledge receipt of the message
});
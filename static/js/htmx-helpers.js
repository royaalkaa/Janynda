document.body.addEventListener("htmx:afterSwap", (event) => {
  const target = event.detail.target;
  if (target && target.dataset.autoclear === "true") {
    setTimeout(() => {
      target.innerHTML = "";
    }, 4500);
  }
});

function getCookie(name) {
  const cookie = document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${name}=`));

  if (!cookie) {
    return null;
  }

  return decodeURIComponent(cookie.split("=").slice(1).join("="));
}

document.body.addEventListener("htmx:configRequest", (event) => {
  const csrfToken = getCookie("csrftoken");
  if (csrfToken) {
    event.detail.headers["X-CSRFToken"] = csrfToken;
  }
});

document.body.addEventListener("htmx:afterSwap", (event) => {
  const target = event.detail.target;
  if (target && target.dataset.autoclear === "true") {
    setTimeout(() => {
      target.innerHTML = "";
    }, 4500);
  }
});

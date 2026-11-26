try {
  var cs = localStorage.getItem("ll-color-scheme");
  if (cs === "light" || cs === "dark") {
    var meta = document.querySelector('meta[name="color-scheme"]');
    if (meta) meta.setAttribute("content", cs);
  }
} catch (e) {}

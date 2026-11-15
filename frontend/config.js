window.EARTHSIGNAL_API_BASE_URL = "";

window.earthSignalApiUrl = (path) => {
  const baseUrl = window.EARTHSIGNAL_API_BASE_URL.replace(/\/+$/, "");
  return `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
};



import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000",
  withCredentials: true, // ✅ SEND COOKIES
});

export default api;










// // frontend/src/lib/api.ts
// import axios from "axios";

// const api = axios.create({
//   baseURL: "http://localhost:8000",
//   withCredentials: true, // 🔥 REQUIRED FOR COOKIE AUTH
//   headers: {
//     "Content-Type": "application/json",
//   },
// });

// export default api;

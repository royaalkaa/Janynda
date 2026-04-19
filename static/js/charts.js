window.JanyndaCharts = {
  renderStepsChart(canvasId, labels, data) {
    const el = document.getElementById(canvasId);
    if (!el || typeof Chart === "undefined") return;

    new Chart(el, {
      type: "bar",
      data: {
        labels,
        datasets: [{
          label: "Шаги",
          data,
          backgroundColor: "#2D9D78",
          borderRadius: 8,
          borderSkipped: false
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, grid: { color: "#E5E7EB" } },
          x: { grid: { display: false } }
        }
      }
    });
  },

  renderBloodPressureChart(canvasId, points) {
    const el = document.getElementById(canvasId);
    if (!el || typeof Chart === "undefined" || !points.length) return;

    new Chart(el, {
      type: "line",
      data: {
        labels: points.map((point) => point.date),
        datasets: [
          {
            label: "Систолическое",
            data: points.map((point) => point.systolic),
            borderColor: "#D63B3B",
            backgroundColor: "rgba(214, 59, 59, 0.08)",
            tension: 0.35
          },
          {
            label: "Диастолическое",
            data: points.map((point) => point.diastolic),
            borderColor: "#E07B39",
            backgroundColor: "rgba(224, 123, 57, 0.08)",
            tension: 0.35
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { beginAtZero: false, grid: { color: "#E5E7EB" } },
          x: { grid: { display: false } }
        }
      }
    });
  },

  renderHeartRateChart(canvasId, points) {
    const el = document.getElementById(canvasId);
    if (!el || typeof Chart === "undefined" || !points.length) return;

    new Chart(el, {
      type: "line",
      data: {
        labels: points.map((point) => point.date),
        datasets: [{
          label: "РџСѓР»СЊСЃ",
          data: points.map((point) => point.bpm),
          borderColor: "#EAB308",
          backgroundColor: "rgba(234, 179, 8, 0.14)",
          tension: 0.35,
          fill: true
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: false, grid: { color: "#E5E7EB" } },
          x: { grid: { display: false } }
        }
      }
    });
  }
};

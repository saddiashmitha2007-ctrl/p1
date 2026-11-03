/**
 * Chart.js Visualizations for Campus Maintenance Reports & Analytics
 */

function initReportCharts(categoryData, statusData, workerData) {
  // 1. Category Breakdown (Doughnut Chart)
  const catCanvas = document.getElementById('categoryChart');
  if (catCanvas && categoryData) {
    const labels = categoryData.map(item => item.category);
    const counts = categoryData.map(item => item.count);

    new Chart(catCanvas, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: counts,
          backgroundColor: [
            '#3b82f6', // Electrical (Blue)
            '#06b6d4', // Plumbing (Cyan)
            '#8b5cf6', // IT (Purple)
            '#f59e0b', // Furniture (Amber)
            '#10b981', // Cleaning (Emerald)
            '#64748b'  // Building (Slate)
          ],
          borderWidth: 2,
          borderColor: '#ffffff'
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            position: 'bottom',
            labels: { boxWidth: 12, padding: 12 }
          }
        }
      }
    });
  }

  // 2. Complaint Status Distribution (Bar Chart)
  const statusCanvas = document.getElementById('statusChart');
  if (statusCanvas && statusData) {
    const sLabels = statusData.map(item => item.status);
    const sCounts = statusData.map(item => item.count);

    new Chart(statusCanvas, {
      type: 'bar',
      data: {
        labels: sLabels,
        datasets: [{
          label: 'Number of Complaints',
          data: sCounts,
          backgroundColor: '#1e3a8a',
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        scales: {
          y: {
            beginAtZero: true,
            ticks: { precision: 0 }
          }
        },
        plugins: {
          legend: { display: false }
        }
      }
    });
  }

  // 3. Worker Workload & Resolved Performance (Horizontal Bar)
  const workerCanvas = document.getElementById('workerChart');
  if (workerCanvas && workerData) {
    const wNames = workerData.map(item => item.name);
    const activeTasks = workerData.map(item => item.active_count);
    const resolvedTasks = workerData.map(item => item.resolved_count || 0);

    new Chart(workerCanvas, {
      type: 'bar',
      data: {
        labels: wNames,
        datasets: [
          {
            label: 'Active Workload',
            data: activeTasks,
            backgroundColor: '#f59e0b',
            borderRadius: 4
          },
          {
            label: 'Resolved Jobs',
            data: resolvedTasks,
            backgroundColor: '#10b981',
            borderRadius: 4
          }
        ]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        scales: {
          x: {
            beginAtZero: true,
            ticks: { precision: 0 }
          }
        },
        plugins: {
          legend: { position: 'bottom' }
        }
      }
    });
  }
}

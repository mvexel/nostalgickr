document.addEventListener('DOMContentLoaded', function() {
  const loaded = new Set();
  const observer = new window.IntersectionObserver((entries, obs) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        console.log('Intersecting:', entry.target);
        const detailsDiv = entry.target;
        const photoId = detailsDiv.id.replace('details-', '');
        if (loaded.has(photoId)) return;
        loaded.add(photoId);
        detailsDiv.innerHTML = '<em>Loading details...</em>';
        detailsDiv.style.display = 'block';
        fetch(`/photo_details/${photoId}`)
          .then(resp => resp.json())
          .then(data => {
            let html = '';
            if (data.error) {
              html = `<span style='color:red;'>${data.error}</span>`;
            } else {
              html = `<strong>Tags:</strong> ${data.tags && data.tags.length ? data.tags.join(', ') : 'None'}<br>`;
              html += `<strong>Views:</strong> ${data.views || 'N/A'}<br>`;
              html += `<strong>Comments:</strong> ${data.comments || '0'}<br>`;
            }
            detailsDiv.innerHTML = html;
          })
          .catch(() => {
            detailsDiv.innerHTML = '<span style="color:red;">Failed to load details.</span>';
          });
        obs.unobserve(detailsDiv);
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.photo-details').forEach(function(div) {
    observer.observe(div);
  });
});

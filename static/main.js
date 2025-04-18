// Add some temporary styles for loading states
const style = document.createElement('style');
style.textContent = `
  .friend-row {
    padding: 1rem;
    border-bottom: 1px solid #eee;
    display: flex;
    align-items: center;
  }
  .friend-info {
    flex-grow: 1;
  }
  .friend-name {
    font-weight: bold;
    margin-bottom: 0.5rem;
  }
  .loading-photo {
    color: #666;
    font-style: italic;
  }
  .photo-loaded {
    display: none; /* Will be shown when photos load */
  }
`;
document.head.appendChild(style);

document.addEventListener('DOMContentLoaded', function() {
  // Initialize IntersectionObserver for lazy loading details
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

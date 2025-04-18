

/**
 * Format timestamp or date string into friendly display (matches Python version).
 * 
 * Examples:
 *   - Today at 3:45 PM
 *   - Yesterday at 11:20 AM
 *   - Apr 15, 2025, 9:00 PM
 *
 * @param {number|string} value - Unix timestamp (number) or date string (YYYY-MM-DD HH:MM:SS)
 * @returns {string} Formatted date string. Returns original value on parse failure.
 * 
 * @see main.py datetimeformat() - Keep logic in sync with Python version
 */
function datetimeformat(value) {
  try {
    let dt;
    if (typeof value === 'number' || (typeof value === 'string' && /^\d+$/.test(value))) {
      dt = new Date(Number(value) * 1000);
    } else if (typeof value === 'string') {
      // Try parsing as "YYYY-MM-DD HH:MM:SS"
      const m = value.match(/(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})/);
      if (m) {
        dt = new Date(
          Number(m[1]), Number(m[2]) - 1, Number(m[3]), Number(m[4]), Number(m[5]), Number(m[6])
        );
      } else {
        return value;
      }
    } else {
      return value;
    }
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const dtDay = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate());
    const yesterday = new Date(today.getTime() - 86400000);
    function pad(num) { return num < 10 ? '0' + num : num; }
    let hour = dt.getHours();
    let ampm = hour >= 12 ? 'PM' : 'AM';
    hour = hour % 12;
    if (hour === 0) hour = 12;
    const minute = pad(dt.getMinutes());
    if (dtDay.getTime() === today.getTime()) {
      return `Today at ${hour}:${minute} ${ampm}`;
    } else if (dtDay.getTime() === yesterday.getTime()) {
      return `Yesterday at ${hour}:${minute} ${ampm}`;
    } else {
      const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      return `${months[dt.getMonth()]} ${dt.getDate()}, ${dt.getFullYear()}, ${hour}:${minute} ${ampm}`;
    }
  } catch (e) {
    return value;
  }
}

/**
 * Main DOM content loaded handler - initializes photo browsing UI.
 * 
 * Handles:
 * - Progressive loading of friends list with photos
 * - Lazy loading of photo details via IntersectionObserver
 * - Thumbnail loading and error handling
 */
document.addEventListener('DOMContentLoaded', function() {
  /**
   * Load and render friends list with latest photos.
   * 
   * Makes API calls to:
   * 1. Fetch latest photos for all friends
   * 2. Batch load photo sizes for thumbnails
   * 3. Lazy load additional details when scrolled into view
   */
  if (window.friendsList && document.getElementById('friends-list')) {
    const friends = window.friendsList;
    const friendsListEl = document.getElementById('friends-list');
    const counterDiv = document.getElementById('dynamic-friends-counter');
    let loadedPhotos = [];
    let completed = 0;
    const total = friends.length;
    if (counterDiv) counterDiv.textContent = `Loaded 0 of ${total} friends...`;

    // Fetch latest photos for all friends
    const nsids = friends.map(f => f.nsid);
    fetch('/friend_latest_photos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(nsids)
    })
    .then(resp => resp.json())
    .then(photosData => {
      // Filter only friends with a photo
      let photoFriends = friends.map(friend => {
        const photo = photosData[friend.nsid];
        if (photo && !photo.error) {
          return { ...photo, friend };
        }
        return null;
      }).filter(Boolean);
      // Sort by most recent upload
      photoFriends.sort((a, b) => parseInt(b.dateupload || 0) - parseInt(a.dateupload || 0));
      if (photoFriends.length === 0) {
        friendsListEl.innerHTML = '<li class="no-photos">No public uploads from friends.</li>';
        if (counterDiv) counterDiv.style.display = 'none';
        return;
      }
      // Render placeholders for each friend with a photo
      friendsListEl.innerHTML = photoFriends.map(photo => `
        <li class="photo-row" data-photo-id="${photo.id}">
          <a href="/photo/${photo.id}" class="thumbnail-placeholder" data-id="${photo.id}"></a>
          <div class="photo-main">
            <div class="photo-title"><a href="/photo/${photo.id}">${photo.title || '(Untitled)'}</a></div>
            <div class="photo-meta">
              <span>Friend: <strong>${photo.friend.realname || photo.friend.username || photo.friend.nsid}</strong></span><br>
              <span>Uploaded: ${photo.dateupload ? datetimeformat(photo.dateupload) : 'N/A'}</span><br>
              <span>Taken: ${photo.datetaken ? datetimeformat(photo.datetaken) : 'N/A'}</span>
            </div>
          </div>
          <div class="photo-extra"><div class="photo-details" id="details-${photo.id}"></div></div>
        </li>
      `).join('');
      // Progressive thumbnail loading
      photoFriends.forEach(photo => {
        fetch('/batch_photo_sizes', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify([photo.id])
        })
        .then(resp => resp.json())
        .then(sizesData => {
          if (sizesData[photo.id]) {
            const square = sizesData[photo.id].find(s => s.label === "Square" || s.label === "Large Square");
            if (square) {
              const img = new window.Image();
              img.src = square.source;
              img.className = 'loaded';
              img.alt = photo.title || '';
              img.onload = function() {
                const placeholder = friendsListEl.querySelector(`.thumbnail-placeholder[data-id="${photo.id}"]`);
                if (placeholder) {
                  placeholder.replaceWith(img);
                }
              };
            }
          }
        });
      });
      if (counterDiv) counterDiv.style.display = 'none';
    });
  }

  /**
   * Initialize IntersectionObserver for lazy loading photo details.
   * 
   * Loads additional metadata (tags, views, comments) only when:
   * - User scrolls the details section into view
   * - Details haven't been loaded already
   * 
   * Uses fetch() to get details from /photo_details/{id} endpoint
   */
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

document.addEventListener('DOMContentLoaded', async () => {
    // Check if we have a stored user ID (simulating login)
    const userId = localStorage.getItem('flickrUserId');
    const authStatus = document.getElementById('auth-status');
    
    if (userId) {
        authStatus.textContent = `Logged in as user ${userId}`;
        loadUserPhotos(userId);
    } else {
        authStatus.textContent = 'Not logged in';
        loadPublicPhotos();
    }

    // Simple login simulation
    authStatus.addEventListener('click', (e) => {
        e.preventDefault();
        if (!userId) {
            const testUserId = '123456789@N00'; // Example Flickr user ID
            localStorage.setItem('flickrUserId', testUserId);
            authStatus.innerHTML = `<a href="#">Logged in as user ${testUserId}</a>`;
            loadUserPhotos(testUserId);
        } else {
            localStorage.removeItem('flickrUserId');
            authStatus.innerHTML = '<a href="#">Log in to Flickr</a>';
            loadPublicPhotos();
        }
    });

    // Load photos initially
    if (!userId) {
        await loadPublicPhotos();
    }
});

async function loadPublicPhotos() {
    try {
        const response = await fetch('/api/public_photos');
        const data = await response.json();
        displayPhotos(data.photos.photo);
    } catch (error) {
        console.error('Error loading public photos:', error);
    }
}

async function loadUserPhotos(userId) {
    try {
        const response = await fetch(`/api/user_photos?user_id=${userId}`);
        const data = await response.json();
        displayPhotos(data.photos.photo);
    } catch (error) {
        console.error('Error loading user photos:', error);
    }
}

function displayPhotos(photos) {
    const container = document.getElementById('photos-container');
    container.innerHTML = '';
    
    photos.forEach(photo => {
        const photoUrl = `https://live.staticflickr.com/${photo.server}/${photo.id}_${photo.secret}_q.jpg`;
        
        const photoElement = document.createElement('div');
        photoElement.className = 'photo';
        photoElement.innerHTML = `
            <img src="${photoUrl}" alt="${photo.title}">
            <div class="title">${photo.title || 'Untitled'}</div>
        `;
        
        container.appendChild(photoElement);
    });
}

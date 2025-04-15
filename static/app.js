document.addEventListener('DOMContentLoaded', async () => {
    // Check if we're logged in by looking for user photos container
    const photosContainer = document.getElementById('photos-container');
    if (photosContainer.dataset.userId) {
        loadUserPhotos(photosContainer.dataset.userId);
    } else {
        loadPublicPhotos();
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

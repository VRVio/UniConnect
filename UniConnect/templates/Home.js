document.addEventListener('DOMContentLoaded', function () {
    const features = document.querySelector('.features');

    function onScroll() {
        const scrollPosition = window.scrollY + window.innerHeight;
        const featuresPosition = features.getBoundingClientRect().top + window.scrollY;

        if (scrollPosition >= featuresPosition) {
            features.classList.add('visible');
            window.removeEventListener('scroll', onScroll);
        }
    }

    window.addEventListener('scroll', onScroll);
});

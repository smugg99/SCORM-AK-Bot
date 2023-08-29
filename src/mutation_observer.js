const slideDiv = document.getElementById('div_Slide');

const observer = new MutationObserver((mutationsList) => {
    for (const mutation of mutationsList) {
        if (mutation.type === 'childList') {
            // Convert added nodes to an array for Python callback
			const addedNodes = Array.from(mutation.addedNodes);
			
            // Call the Python callback function with added nodes
            window.pyCallback(addedNodes);
			
			break;
        }
    }
});

const observerConfig = { childList: true };
observer.observe(slideDiv, observerConfig);
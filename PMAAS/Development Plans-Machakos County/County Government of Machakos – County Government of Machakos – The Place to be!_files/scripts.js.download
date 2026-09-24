(function($){
    "use strict";

    /* Dicrectory Single Google Map */
    async function initMap() {
        const ovaMap    = document.getElementById("ova_dir_single_google_map");
        if (! ovaMap ) {return;}
        const dataMap       = JSON.parse(ovaMap.getAttribute('data-map'));
        const latitude      = parseFloat(dataMap.latitude);
        const longitude     = parseFloat(dataMap.longitude);
        const zoom          = parseInt(dataMap.zoom);
        const map = new google.maps.Map(document.getElementById("ova_dir_single_google_map"), {
            center: { lat: latitude, lng: longitude },
            zoom: zoom,
            mapTypeControl: false,
        });
        if ( latitude && longitude ) {
            const marker = new google.maps.Marker({
                map,
                anchorPoint: new google.maps.Point(0, -29),
                position: { lat: latitude, lng: longitude },
            });
        }
    }

    /* Directory Archive Google Map */
    async function initMap2() {
        const ovaMap    = document.getElementById("ova_dir_archive_google_map");
        if (! ovaMap ) {return;}
        const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");
        const dataMap   = JSON.parse(ovaMap.getAttribute('data-map'));
        const latitude  = parseFloat(dataMap.latitude);
        const longitude = parseFloat(dataMap.longitude);
        const zoom = parseInt(dataMap.zoom);
        const properties = JSON.parse(ovaMap.getAttribute('data-properties'));
        var markers     = [];
        var latitudes   = [];
        var longitudes  = [];
        if ( properties.length ) {
            for (const property of properties) {
                if ( property.position.lat != '' && property.position.lng != '' ) {
                    let latitude = parseFloat(property.position.lat);
                    let longitude = parseFloat(property.position.lng);
                    const marker = new google.maps.marker.AdvancedMarkerElement({
                        content: buildContent(property),
                        position : { lat: latitude, lng: longitude },
                        title: property.title,
                    });

                    marker.addListener("click", () => {
                        toggleHighlight(marker, property);
                    });

                    markers.push(marker);
                    latitudes.push(latitude);
                    longitudes.push(longitude);
                }
            }

        } else {
            const marker = new google.maps.marker.AdvancedMarkerElement({
                position : { lat: latitude, lng: longitude },
            });
            markers.push(marker);
        }

        var positionCenter = {};
        if ( latitudes.length > 0 && longitudes.length > 0 ) {
            positionCenter = { lat: average(latitudes), lng: average(longitudes) };
        } else {
            positionCenter = { lat: latitude, lng: longitude };
        }
        const map = new google.maps.Map(document.getElementById("ova_dir_archive_google_map"), {
            zoom: zoom,
            center: positionCenter,
            mapId: "ova_dir_archive_google_map",
        });

        new markerClusterer.MarkerClusterer({ markers, map });

        function average(arr){
            const sum = arr.reduce((a, b) => a + b, 0);
            const avg = (sum / arr.length) || 0;
            return avg;
        }

        function toggleHighlight(markerView, property) {
            if (markerView.content.classList.contains("highlight")) {
                markerView.content.classList.remove("highlight");
                markerView.zIndex = null;
            } else {
                markerView.content.classList.add("highlight");
                markerView.zIndex = 1;
            }
        }

        function buildContent(property) {
            const content = document.createElement("div");

            content.classList.add("property");
            var categoryContent = '';
            if ( property.terms ) {
                const terms = property.terms;
                for (let i = 0; i < terms.length; i++) {
                    let separator = i + 1 < terms.length ? ', ' : '';
                    categoryContent += `<a href="${terms[i].url}" title="${terms[i].name}">${terms[i].name}</a>${separator}`;
                }
            }
            
            content.innerHTML = `
                <div class="avatar">
                    <img src="${property.thumbnail}" alt="${property.image_alt}" />
                </div>
                <div class="card">
                    <a href="${property.url}" class="thumbnail" title="${property.title}">
                        <img src="${property.thumbnail}" alt="${property.image_alt}" />
                    </a>
                    <div class="content">
                        <h2 class="title">
                            <a href="${property.url}" title="${property.title}">${property.title}</a>
                        </h2>
                        <ul class="info">
                            <li>
                                <i class="fas fa-map-marker-alt" aria-hidden="true"></i>
                                <div class="text">${property.address}</div class="text">
                            </li>
                            <li>
                                <i class="far fa-folder" aria-hidden="true"></i><div class="text">${categoryContent}</div>
                            </li>
                        </ul>
                    </div>
                </div>
                `;
            return content;
        }
    }

    initMap();
    initMap2();
    if ( $('[data-fancybox="gallery"]').length ) {
        Fancybox.bind('[data-fancybox="gallery"]', {
        }); 
    }

}) (jQuery);
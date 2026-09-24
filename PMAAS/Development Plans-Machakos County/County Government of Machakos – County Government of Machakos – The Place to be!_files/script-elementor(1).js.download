(function($){
	"use strict";

	$(window).on('elementor/frontend/init', function () {

		/* Category */
		elementorFrontend.hooks.addAction('frontend/element_ready/ova_dir_category.default', function(){
			$(".ova-dir-category").each(function(e){
				var icon = $(this).find(".item i");
				icon.click(function(e){
					e.preventDefault();
					e.stopPropagation();
					var cateChild = $(this).parent().next();
					if ( $(this).attr("class") == "fas fa-plus" ) {
						$(this).attr("class", "fas fa-minus");
					} else {
						$(this).attr("class", "fas fa-plus");
					}
					cateChild.slideToggle();
				});
			});
		});

		/* Archive */
		elementorFrontend.hooks.addAction('frontend/element_ready/ova_dir_archive.default', function(){
			async function initMap2() {
				const ovaMap    = document.getElementById("el_ova_dir_archive_google_map");
				if (! ovaMap ) {return;}
				const { Map } = await google.maps.importLibrary("maps");
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
				const map = new google.maps.Map(document.getElementById("el_ova_dir_archive_google_map"), {
					zoom: zoom,
					center: positionCenter,
					mapId: "el_ova_dir_archive_google_map",
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
						<img src="${property.thumbnail}" />
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
									<i class="fas fa-map-marker-alt" aria-hidden="true"></i><div class="text">${property.address}</div class="text">
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
			initMap2();
			$('.ova-dir-archive .list-cat-dir .cate_name').on("click",function(e){
				e.preventDefault();
				var id          = $(this).attr("data-id");
				var dataQuery	= $(".ova-dir-archive").attr("data-query");
				var dataShow	= $(".ova-dir-archive").attr("data-show");
				var items       = $(".ova-dir-archive .list-cat-dir .item");
				var item        = $(this).parent();
				var loader      = $(".ova-dir-archive .ova-dir-loader .loader");
				var directoryContent = $(".ova-dir-archive .ova_dir_archive_content");
				items.removeClass("active");
				item.addClass("active");
				loader.addClass("is-active");
				directoryContent.addClass("overlay");
				$.ajax({
					type: "post",
					dataType: "html",
					url: ova_dir_ajax_object.ajax_url,
					data: {
						action: 'ova_dir_cate_show_list',
						id: id,
						query: JSON.parse(dataQuery),
						show: JSON.parse(dataShow),
					},
					success: function(response){
						loader.removeClass("is-active");
						directoryContent.removeClass("overlay");
						directoryContent.html(response);
						initMap2();
					},
					error: function(err){
						console.log(err);
					}
				});
			});
			$(document).on('click', ".ova_dir_pagination_ajax .page-numbers", function (e) {    
		        e.preventDefault();
		        var dataArgs    = $(document).find(".ova_dir_pagination_ajax").attr("data-args");
		        var args        = JSON.parse( dataArgs );
		        var showArgs  	= $(this).closest('.ova-dir-archive').attr('data-show');
		        var offset      = parseInt( $(this).attr("data-offset") );
		        var page        = parseInt( $(this).attr("data-page") );
		        var directoryContent = $(".ova-dir-archive .ova_dir_archive_content");
		        var loader      = $(".ova-dir-archive .ova-dir-loader .loader");
		        if (page) {
		            loader.addClass("is-active");
		            directoryContent.addClass("overlay");
		            $('html, body').animate({
		                scrollTop: $(".ova-dir-archive").offset().top
		            });
		            $.ajax({
		                type: "post",
		                dataType: "html",
		                url: ova_dir_ajax_object.ajax_url,
		                data: {
		                    action: 'ova_dir_pagination_ajax',
		                    args: args,
		                    offset: offset,
		                    page: page,
		                    show: JSON.parse(showArgs),
		                },
		                success: function(response){
		                    loader.removeClass("is-active");
		                    directoryContent.removeClass("overlay");
		                    directoryContent.html(response);
		                    initMap2();
		                }
		            });
		        }
		    });
		});

});
})(jQuery);

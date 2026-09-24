(function($){
   "use strict";
   $(document).ready(function(){

      /***** Map *****/
      function initialize() {
         var lat = parseFloat( $("#location").data('lat') );
         var lng = parseFloat( $("#location").data('lng') );
         var address = $("#location").data('address');
         var zoom = parseInt( $("#location").data('zoom') );

         var infoWindow = new google.maps.InfoWindow();

         var loc = {lat: lat, lng: lng};

         var map = new google.maps.Map(document.getElementById('location'), {
            zoom: zoom,
            center: loc,
            scrollwheel: false
         });

         var marker = new google.maps.Marker({
            position: loc,
            map: map
         });    

         google.maps.event.addListener(marker, 'click', (function(marker) {
            return function() {
               infoWindow.setContent(address);
               infoWindow.open(map, marker);
            }
         })(marker));

      }

      
      if( typeof google !== 'undefined' && $(".single-event #location").length > 0 ){ 
         google.maps.event.addDomListener(window, "load", initialize);
      }
      


      /***** Gallery PrettyPhoto *****/
      if( $(".gallery-items a[data-rel^='prettyPhoto']").length > 0 ){
         $(".gallery-items a[data-rel^='prettyPhoto']").prettyPhoto();
      }


      /***** Date Time Picker *****/
      $(".ovaev_start_date_search, .ovaev_end_date_search").each(function(){
         if($().datetimepicker) {
            var date = $(this).data('date');
            var lang = $(this).data('lang');
            var dayOfWeekStart = $(this).data('start-of-week');

            $(this).datetimepicker({
               format: date,
               timepicker:false,
               dayOfWeekStart: dayOfWeekStart,
            });
            $.datetimepicker.setLocale(lang);
         }
      });

      $(".slide-event-feature").each(function(){
         var rtl = false;
         if ( $('body').hasClass('rtl') ) {
            rtl = true;
         }
         $(this).owlCarousel({
            loop:true,
            margin:80,
            nav:false,
            dots:false,
            autoplay:true,
            autoplayTimeout:4000,
            autoplayHoverPause:true,
            rtl:rtl,
            responsive:{
               0:{
                  items:1
               },
               600:{
                  items:1
                },
               1000:{
                  items:1
               }
            }
         });
      })


      $('.search_archive_event #ovaev_type').on('change', function(){
         $(this).closest('.search_archive_event').find('.select2-selection__rendered').css('color', '#333');
      });


      $('.single_event .event_content .tab-Location ul.nav li.nav-item:first-child a').addClass('active');
      $('.single_event .event_content .tab-Location .tab-content .tab-pane:first-child').addClass('active').removeClass('fade');



   });

})(jQuery);
(function($){
	"use strict";
	

	$(window).on('elementor/frontend/init', function () {

      /* Upcomming Event Slide */

      elementorFrontend.hooks.addAction('frontend/element_ready/ova_events_cat.default', function(){

         if( $('.event-slide-owl').length > 0 ){  
            $('.event-slide-owl').each(function(){

               var event_sl = $(this).data('options');
               var rtl            = false;

               if( $('body').hasClass('rtl') ){
                  rtl = true;
               }

               $(this).owlCarousel({
                  margin: event_sl.margin,
                  smartSpeed: event_sl.smartSpeed,
                  loop: event_sl.loop, 				        
                  autoplay: event_sl.autoplay,
                  autoplayTimeout: event_sl.autoplayTimeout,
                  autoplayHoverPause: event_sl.autoplayHoverPause,
                  dots: event_sl.dots,  
                  nav: event_sl.nav,
                  slideBy: event_sl.slideBy,
                  navText:[event_sl.prev,event_sl.next],
                  rtl: rtl,
                  lazyLoad: true,						
                  responsive:{
                     0:{
                        items: event_sl.items_mobile
                     },
                     768:{
                        items: event_sl.items_ipad
                     },
                     1170:{
                        items: event_sl.total_columns_slide,
                     }
                  }
               });				 	
            });				
         }

      });

      elementorFrontend.hooks.addAction('frontend/element_ready/ova_events_slide.default', function(){
         $(".ovaev-slide").each(function(){
              var owlsl = $(this) ;
              var owlsl_ops = owlsl.data('options') ? owlsl.data('options') : {};

              var responsive_value = {
                  0:{
                    items:1,
                    nav:false
                  },
                  576:{
                    items:1

                  },
                  992:{
                    items:2,
                    nav:false
                  },
                  1170:{
                    items:owlsl_ops.items
                  }
              };
              
              owlsl.owlCarousel({
                autoWidth: owlsl_ops.autoWidth,
                margin: owlsl_ops.margin,
                items: owlsl_ops.items,
                loop: owlsl_ops.loop,
                autoplay: owlsl_ops.autoplay,
                autoplayTimeout: owlsl_ops.autoplayTimeout,
                center: owlsl_ops.center,
                nav: owlsl_ops.nav,
                dots: owlsl_ops.dots,
                thumbs: owlsl_ops.thumbs,
                autoplayHoverPause: owlsl_ops.autoplayHoverPause,
                slideBy: owlsl_ops.slideBy,
                smartSpeed: owlsl_ops.smartSpeed,
                navText:[
                '<i class="arrow_carrot-left" ></i>',
                '<i class="arrow_carrot-right" ></i>'
                ],
                responsive: responsive_value,
              });

              /* Fixed WCAG */
              owlsl.find(".owl-nav button.owl-prev").attr("title", "Previous");
              owlsl.find(".owl-nav button.owl-next").attr("title", "Next");
              owlsl.find(".owl-dots button").attr("title", "Dots");

            });
      });
       /* Project Grid */
      elementorFrontend.hooks.addAction('frontend/element_ready/ova_events_grid.default', function(){
         var slide = $('.ovapo_project_slide .grid ');
         var data = $('.ovapo_project_slide .grid ').data('owl');

         if (slide.length > 0) {
            slide.owlCarousel(
               data
               );
            /* Fixed WCAG */
            slide.find(".owl-nav button.owl-prev").attr("title", "Previous");
            slide.find(".owl-nav button.owl-next").attr("title", "Next");
            slide.find(".owl-dots button").attr("title", "Dots");
         }

         $('.ovapo_project_grid .button-filter button:first-child').addClass('active');
         var button = $('.ovapo_project_grid .button-filter');
         button.each(function() {
            button.on('click', 'button', function() {
               button.find('.active').removeClass('active');
               $(this).addClass('active');
            });
         });

         button.on('click', 'button', function(e) {
            e.preventDefault();

            var filter = $(this).data('filter');
            var order = $(this).data('order');
            var orderby = $(this).data('orderby');
            var number_post = $(this).data('number_post');
            var column = $(this).data('column');
            var first_term = $(this).data('first_term');
            var term_id_filter_string = $(this).data('term_id_filter_string');
            var show_featured = $(this).data('show_featured');
            var showFields = $(this).closest('.ovapo_project_grid').find('input[name="ovaev-show-fields"]').val();

            $(this).parents('.ovapo_project_grid').find('.wrap_loader').fadeIn(100);

            

            $.ajax({
               url: ajax_object.ajax_url,
               type: 'POST',
               data: ({
                  action: 'filter_elementor_grid',
                  filter: filter,
                  order: order,
                  orderby: orderby,
                  number_post: number_post,
                  column: column,
                  first_term: first_term,
                  term_id_filter_string: term_id_filter_string,
                  show_featured: show_featured,
                  show_fields: showFields ? $.parseJSON( showFields ) : ''
               }),
               success: function(response){

                  $('.ovapo_project_grid .wrap_loader').fadeOut(200);

                  var items = $('.ovapo_project_grid .items');

                  items.html( response ).fadeIn(300);
                  feather.replace();

                  items.trigger('destroy.owl.carousel');
                  items.owlCarousel(data);

               },
            })
         });

      }); 

     

  /*Calendar*/
  elementorFrontend.hooks.addAction('frontend/element_ready/ova_events_calen.default', function(){

          $(document).ready(function(){


           var calendars = {};

            $('.ovaev_events_calendar').each( function( e){
            
               
              var thisMonth = moment().format('YYYY-MM');

               var id = $(this).data('id');
               var firstDay = $(this).data('first-day');
               var daysOfTheWeek = $(this).data('days-of-the-week');

               id = id.replace(/\s/g, '');

               var srcCalendarEl = document.getElementById(id);
              
               

               if( srcCalendarEl === null ) return;

               var events = '';
               var date_rent_full = [];
               events = srcCalendarEl.getAttribute('events');


               if( events && events.length > 0 ){
                 events = JSON.parse( events );
              }


             
              // Events to load into calendar
     

              calendars.clndr1 = $('.cal1').clndr({
                  weekOffset: firstDay,
                  daysOfTheWeek: daysOfTheWeek,
                  events: events,
                  clickEvents: {
                      click: function (target) {
                          var eve =  target.events;
                          location.assign(eve[0].url);
                      },
                      
                  },

                  multiDayEvents: {
                      singleDay: 'date',
                      endDate: 'endDate',
                      startDate: 'startDate'
                  },
                  showAdjacentMonths: true,
                  adjacentDaysChangeMonth: false
              
              });

               $(document).keydown( function(e) {
                  // Left arrow
                  if (e.keyCode == 37) {
                      calendars.clndr1.back();
                  }

                  // Right arrow
                  if (e.keyCode == 39) {
                      calendars.clndr1.forward();
                  }
              });



            });

          });


        });

   });
})(jQuery);

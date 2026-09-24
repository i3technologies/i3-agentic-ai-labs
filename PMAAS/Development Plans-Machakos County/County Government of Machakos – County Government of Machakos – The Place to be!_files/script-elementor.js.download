(function($){
	"use strict";

	$(window).on('elementor/frontend/init', function () {

		
		/* Form email */
      elementorFrontend.hooks.addAction('frontend/element_ready/ova_form_mail.default', function(){
         $('.ova-form-mail input[type="submit"]').on('click', function(e){

            var that = $(this);
            var flag = true;
            $('.ova-form-mail .con .input .error').css({'display':'none'});
            that.closest('.ova-form-mail').find('.field').each(function( index ){
               if( $(this).hasClass('required') && $(this).val() == '' ){
                  flag = false;
                  $(this).parent('.input').children('.error').css({'display':'block'});
               }
            });

            if( ! flag ){
               e.preventDefault();
               return false;
            }
            
         })
      });
      /* end Form email */	

      /* ova_archive_dep_slide */
      elementorFrontend.hooks.addAction('frontend/element_ready/ova_archive_dep_slide.default', function(){
         $(".ova_dep_slide").each(function(){
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
                    items:2
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
                '<i class="fa fa-angle-left" ></i>',
                '<i class="fa fa-angle-right" ></i>'
                ],
                responsive: responsive_value,
              });

              /* Fixed WCAG */
              owlsl.find(".owl-nav button.owl-prev").attr("title", "Previous");
              owlsl.find(".owl-nav button.owl-next").attr("title", "Next");
              owlsl.find(".owl-dots button").attr("title", "Dots");

            });
      });
      /* end ova_archive_dep_slide */	

   });
})(jQuery);

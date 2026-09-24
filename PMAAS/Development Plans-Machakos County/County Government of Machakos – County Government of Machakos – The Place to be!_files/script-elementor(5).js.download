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

   });
})(jQuery);

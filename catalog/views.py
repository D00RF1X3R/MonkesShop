from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.db.models import Q, Min, Max, Count
from catalog.models import Product, ProductImage
from business.models import Seller, SellerData
from core.models import Universe, Category
from users.models import Rating, Cart, CustomerData
from django.template.loader import render_to_string
from django.views.generic import TemplateView, View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt



@method_decorator(csrf_exempt, name='dispatch')
class ProductListView(TemplateView):
    template_name = 'catalog\catalog.html'
    def post(self, request):
        product = get_object_or_404(Product, id=request.POST.get("id"))
        try:
            customer_data = CustomerData.objects.get(user=request.user)
        except CustomerData.DoesNotExist:
            customer_data = None
        action_type = request.POST.get("action")
        if action_type == 'favorite' and customer_data:
            if product in customer_data.favorite_products.all():
                customer_data.favorite_products.remove(product)
            else:
                customer_data.favorite_products.add(product)
        elif action_type == 'to_cart' and customer_data:
            Cart.objects.get_or_create(
                customer=customer_data.user,
                product=product,
                count=1,
            )
        elif action_type and not customer_data:
            return HttpResponseRedirect("/users/login")
        data = render_to_string("catalog/catalog.html", {"product": product, "customer": customer_data, "type": action_type})
        return JsonResponse({"data": data, "is_favorite": product in customer_data.favorite_products.all()})
        
    def get_context_data(self):
        context = {}
        search_query = self.request.GET.get("q")
        products = Product.objects.all()
        context["products"] = products
        if search_query:
            q = None
            for word in search_query.split():
                q_aux = Q( name__icontains = word )
                q = ( q_aux & q ) if bool( q ) else q_aux
            context["products"] = products.filter(q)
            context["current_search"] = search_query

        context["categories"] = Category.objects.all()
        context["universes"] = Universe.objects.all()
        context["sellers"] = Seller.objects.all()
        min_max_price = Product.objects.aggregate(Min("price"), Max("price"))
        context["min_max_price"] = min_max_price
        if min_max_price["price__min"] or min_max_price["price__max"]:
            products = products.filter(price__gte=min_max_price["price__min"])
            products = products.filter(price__lte=min_max_price["price__max"]).order_by("-price")
        return context
    def get_popular_products(self):
        context = self.get_context_data()
        context["products"] = Product.objects.annotate(num_marks=Count('marks')).order_by('-num_marks')
    def get_nonpopular_products(self):
        context = self.get_context_data()
        context["products"] = Product.objects.annotate(num_marks=Count('marks')).order_by('num_marks')

@method_decorator(csrf_exempt, name='dispatch')
class ProductDetailView(TemplateView):
    template_name = 'catalog\product.html'
    def post(self, request, id):
        product = get_object_or_404(Product, id=id)
        customer_data = get_object_or_404(CustomerData, user=request.user)
        Cart.objects.get_or_create(
            customer=customer_data.user,
            product=product,
            count = 1,
        )
        data = render_to_string("product/product.html", {"product": product, "customer": customer_data})
        return JsonResponse({"data": data})
    def get_context_data(self, id):
        context = super().get_context_data()
        product = get_object_or_404(Product.objects.filter(id=id))
        product_marks = Rating.objects.filter(product=id).values_list('mark', flat=True)
        if product_marks:
            marks_count = len(product_marks)
            product_rating = sum(product_marks)/marks_count
        else:
            product_rating = 0
            marks_count = 0
        context["product"] = product
        context["images"] = ProductImage.objects.filter(product=id)
        context["product_rating"] = product_rating
        context["marks_count"] = marks_count
        context["is_verified"] = get_object_or_404(SellerData.objects.filter(user=product.seller)).is_verified
        return context
    
@method_decorator(csrf_exempt, name='dispatch')
class filter_product(View):
    def post(self, request):
        product = get_object_or_404(Product, id=request.POST.get("id"))
        try:
            customer_data = CustomerData.objects.get(user=request.user)
        except CustomerData.DoesNotExist:
            customer_data = None
        Cart.objects.get_or_create(
            customer=customer_data.user,
            product=product,
            count=1,
        )
        data = render_to_string("catalog/async/catalog.html", {"product": product, "customer": customer_data})
        return JsonResponse({"data": data, "is_favorite": product in customer_data.favorite_products.all()})

    def get(self, request):
        sortid = request.GET.get("sortid")
        universes = request.GET.getlist("universe[]")
        categories = request.GET.getlist("category[]")
        sellers = request.GET.getlist("seller[]")
        min_price = int(request.GET.get("min_price"))
        max_price = int(request.GET.get("max_price"))
        search_query = request.GET.get("q")
        
        if sortid == "populate-low":
            products = Product.objects.all()
            products = products.annotate(cnt=Count('marks')).order_by('cnt')
        elif sortid == "populate-high":
            products = Product.objects.all()
            products = products.annotate(cnt=Count('marks')).order_by('-cnt')
        else:
            products = Product.objects.all()
        if len(universes) > 0:
            products = products.filter(universe__id__in=universes).distinct()
        if len(categories) > 0:
            products = products.filter(category__id__in=categories).distinct()
        if len(sellers) > 0:
            products = products.filter(seller__id__in=sellers).distinct()
        if search_query:
            q_aux = Q(name__icontains=search_query)
            products = products.filter(q_aux)
        if min_price and max_price:
            if max_price > min_price:
                products = products.filter(price__gte=min_price)
                products = products.filter(price__lte=max_price).order_by("price")
            else:
                products = products.filter(price__gte=max_price)
                products = products.filter(price__lte=min_price).order_by("-price")


        data = render_to_string("catalog/async/catalog.html", {"products": products})
        return JsonResponse({"data": data, })

